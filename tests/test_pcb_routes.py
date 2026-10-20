"""PCB-015C0 source-route contract; small Gerbonara images, no native/mesh."""
from dataclasses import replace
from hashlib import sha256
from math import hypot
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from gerbonara import GerberFile
from antenna_lab.core.config import ConfigurationError
from antenna_lab.pcb.gerber import _copper
from antenna_lab.pcb.model import BoardOutline, PcbGeometry, Substrate, PcbPort
from antenna_lab.pcb.routes import audit_routes
from antenna_lab.pcb.grid import PcbGrid
from antenna_lab.pcb.geometry_resolution import apply_geometry_resolution
from antenna_lab.pcb.transform import normalize_port_orientation, inverse_transform_geometry
from antenna_lab.solvers.reduced_pcb import extract_trace_sections, detect_coupled_sections

HEADER='%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.2*%\nD10*\nG01*\n'
LINE='X1000000Y0D02*\nX5000000Y0D01*\n'

def image(body):
    text=HEADER+body+'M02*\n';routes=[]
    copper=_copper(GerberFile.from_string(text),routes=routes,
        source_file='fixture.GTL',source_sha256=sha256(text.encode()).hexdigest())
    return copper,tuple(routes)


def geometry(body):
    copper,routes=image(body)
    board=BoardOutline(((-.01,-.01),(.01,-.01),(.01,.01),(-.01,.01)))
    # A logical port at the outer caps, used only for normalization/projection;
    # a reduced solve would still require its full-width physical feed audit.
    return PcbGeometry('pcb',board,copper,Substrate(board,-.001,0,4.3,0),
        PcbPort('source',(-.0009,0),(.0009,0),.0002),
        routes=routes,route_provenance_available=True)


class RouteTests(unittest.TestCase):
    def test_line_axis_width_source_and_oblique_guard(self):
        g=geometry('X-5000000Y0D02*\nX-1000000Y0D01*\n'
                   'X1000000Y0D02*\nX4000000Y4000000D01*\n')
        sections,evidence=extract_trace_sections(g)
        line=next(s for s in sections if s.start_xy_m[0]>0)
        self.assertAlmostEqual(line.length_m,.005,places=14)
        self.assertEqual(line.start_xy_m,(.001,0))
        self.assertEqual(line.stop_xy_m,(.004,.004))
        self.assertEqual(line.width_m,.0002)
        self.assertTrue(all(r['source_status']=='verified' for r in evidence))
        self.assertTrue(all(len(r['source_sha256'])==64 for r in evidence))
        with self.assertRaisesRegex(ConfigurationError,'oblique coupling analysis unsupported'):
            detect_coupled_sections(sections)
        with self.assertRaisesRegex(ConfigurationError,'no Cartesian axis'):_=line.axis
        json.dumps(g.as_dict(),allow_nan=False)

    def test_dark_clear_restore_and_no_unverified_tl(self):
        clear='%LPC*%\n%ADD11C,0.4*%\nD11*\nX3000000Y0D03*\n'
        g=geometry(LINE+clear)
        self.assertEqual(g.routes[0].status,'ambiguous_conductor')
        with self.assertRaisesRegex(ConfigurationError,'clear/restore'):
            extract_trace_sections(g)
        g=geometry(LINE+clear+'%LPD*%\nD10*\n'+LINE)
        self.assertEqual(len(g.copper),1)
        self.assertTrue(all(r.status=='verified' for r in g.routes))
        sections,_=extract_trace_sections(g)
        self.assertEqual(len(sections),1) # restored/duplicate overdraw not a second TL
        self.assertEqual(len(sections[0].feature_ids),2)

    def test_partial_clear_without_disconnection_is_rejected(self):
        g=geometry(LINE+'%LPC*%\n%ADD11C,0.1*%\nD11*\nX3000000Y90000D03*\n')
        self.assertEqual(len(g.copper),1)
        self.assertEqual(g.routes[0].status,'stroke_not_preserved')
        with self.assertRaisesRegex(ConfigurationError,'stroke_not_preserved'):extract_trace_sections(g)

    def test_arc_preserved_with_absolute_center_and_explicit_error(self):
        g=geometry('G75*\nX1000000Y0D02*\nG03X2000000Y1000000I0J1000000D01*\n')
        r=g.routes[0]
        self.assertEqual(r.kind,'Arc');self.assertEqual(r.center_xy_m,(.001,.001))
        self.assertFalse(r.clockwise)
        with self.assertRaisesRegex(ConfigurationError,r'Arc unsupported.*route_000001.*fixture.GTL'):
            extract_trace_sections(g)

    def test_flash_region_not_promoted_and_no_legacy_fallback(self):
        g=geometry('X1000000Y0D03*\n')
        self.assertEqual(g.routes,())
        with self.assertRaisesRegex(ConfigurationError,'flashes/regions are not transmission lines'):
            extract_trace_sections(g)

    def test_transform_and_shared_projection_preserve_detached_provenance(self):
        g=geometry('X-5000000Y0D02*\nX-1000000Y0D01*\n'+LINE+
                   '%ADD11R,0.2X0.2*%\nD11*\nX-1000000Y0D03*\nX1000000Y0D03*\n')
        # rotate once to a vertical source, then production normalization once
        from antenna_lab.pcb.transform import _map_xy
        g=_map_xy(g,lambda p:(-p[1]+.002,p[0]+.003))
        before=g.as_dict();n,t=normalize_port_orientation(g)
        restored=inverse_transform_geometry(n,t)
        for a,b in zip(g.routes,restored.routes):
            self.assertLess(hypot(*(x-y for x,y in zip(a.start_xy_m,b.start_xy_m))),1e-14)
            self.assertEqual(a.source_sha256,b.source_sha256)
        modeled,ticks,_=apply_geometry_resolution(n,PcbGrid())
        self.assertEqual(before,g.as_dict())
        self.assertEqual(len(ticks.routes),2)
        self.assertTrue(all(r.status=='verified' for r in modeled.routes))
        self.assertEqual(len(extract_trace_sections(modeled)[0]),2)
        for r in modeled.routes:
            for p in (r.start_xy_m,r.stop_xy_m,*r.footprint_xy_m):
                self.assertEqual(p,tuple(ticks.grid.to_metres(ticks.grid.nearest_tick(v)) for v in p))
        self.assertEqual(modeled.routes[0].source_sha256,g.routes[0].source_sha256)

    def test_reaudit_final_copper_does_not_trust_cached_owner(self):
        g=geometry(LINE);c=g.copper[0]
        # a second independent record makes the owner ambiguous even if a
        # stale route claims the first ID; no reliance on metadata alone.
        changed=g.copper+[replace(c,id='other')]
        audited=audit_routes(g.routes,changed)
        self.assertNotEqual(audited[0].status,'verified')

    def test_multilayer_folder_route_ids_and_hashes(self):
        from antenna_lab.pcb.bundle import load_bundle_geometry
        region='G36*\nX-9000000Y-9000000D02*\nX9000000Y-9000000D01*\nX9000000Y9000000D01*\nX-9000000Y9000000D01*\nX-9000000Y-9000000D01*\nG37*\n'
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'board.GTL').write_text(HEADER+'X-5000000Y0D02*\nX-1000000Y0D01*\n'+LINE+'%ADD11R,0.2X0.2*%\nD11*\nX-1000000Y0D03*\nX1000000Y0D03*\nM02*\n')
            (root/'board.GBL').write_text(HEADER+region+'M02*\n')
            (root/'board.GKO').write_text(HEADER+region.replace('G36*\n','').replace('G37*\n','')+'M02*\n')
            physical=dict(schema_version=2,stackup=[
                dict(type='copper',role='top',model='pec',thickness_um=35,conductivity_s_m=58e6),
                dict(type='dielectric',name='core',thickness_mm=1,epsilon_r=4.3,loss_tangent=0),
                dict(type='copper',role='bottom',model='pec',thickness_um=35,conductivity_s_m=58e6)],
                port=dict(mode='explicit',layer='top',negative_mm=[-.9,0],positive_mm=[.9,0],width_mm=.01))
            _,g,_=load_bundle_geometry(root,physical_value=physical)
            self.assertTrue(g.route_provenance_available)
            self.assertEqual(len(g.routes),2)
            self.assertTrue(all(r.conductor_id.startswith('top:') for r in g.routes))
            self.assertEqual(g.routes[0].source_sha256,sha256((root/'board.GTL').read_bytes()).hexdigest())


if __name__=='__main__':unittest.main()
