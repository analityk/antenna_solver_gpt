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


def projection_case(quantum):
    """Same physical edge, independently tessellated evidence before projection.

    The extra collinear footprint vertex rounds to a stair-step outside the
    projected outer edge. There is no physical hole, width loss or new owner.
    """
    from antenna_lab.pcb.model import CopperPolygon, PcbRoute
    g=geometry('X-5000000Y0D02*\nX-1000000Y0D01*\n'+LINE+
        '%ADD11R,0.2X0.2*%\nD11*\nX-1000000Y0D03*\nX1000000Y0D03*\n')
    y0=.0001+.4*quantum;y1=.0001+.6*quantum
    outer=((.0009,-.0001),(.0051,-.0001),(.0051,y1),(.0009,y0))
    middle=(.003,(y0+y1)/2)
    footprint=outer[:3]+(middle,)+outer[3:]
    right=next(c for c in g.copper if c.vertices_xy_m[0][0]>0)
    replacement=CopperPolygon(right.id,outer,0,'top')
    g.copper=[replacement if c.id==right.id else c for c in g.copper]
    r=next(r for r in g.routes if r.conductor_id==right.id)
    r=replace(r,start_xy_m=(.001,0),stop_xy_m=(.005,0),
              footprint_xy_m=footprint,footprint_holes_xy_m=())
    g.routes=audit_routes(tuple(r if v.id==r.id else v for v in g.routes),g.copper,initial=True)
    return g,r.id


class ProjectedRouteTests(unittest.TestCase):
    def test_independent_tessellations_do_not_define_physical_survival(self):
        from antenna_lab.pcb.routes import route_footprint
        from antenna_lab.pcb.regions import copper_shape
        for quantum_nm in (10000,1000):
            with self.subTest(quantum_nm=quantum_nm):
                grid=PcbGrid(quantum_nm);g,rid=projection_case(grid.quantum_m)
                before=g.as_dict()
                modeled,ticks,audit=apply_geometry_resolution(g,grid)
                self.assertEqual(audit['topology_status'],'PASS')
                route=next(r for r in modeled.routes if r.id==rid)
                owner=next(c for c in modeled.copper if c.id==route.conductor_id)
                self.assertGreater(route_footprint(route).difference(copper_shape(owner)).area,0)
                self.assertEqual(route.source_status,'verified')
                self.assertEqual(route.status,'verified')
                self.assertTrue(ticks.topology_audit_sha256)
                self.assertEqual(len(extract_trace_sections(modeled)[0]),2)
                self.assertEqual(g.as_dict(),before)
                json.dumps(modeled.as_dict(),allow_nan=False)

    def test_arc_survival_precedes_explicit_unsupported_guard(self):
        body=('X-5000000Y0D02*\nX-1000000Y0D01*\n'+LINE+
              'G75*\nG03X6000000Y1000000I0J1000000D01*\n'+
              '%ADD11R,0.2X0.2*%\nD11*\nX-1000000Y0D03*\nX1000000Y0D03*\n')
        for nm in (10000,1000):
            with self.subTest(quantum_nm=nm):
                modeled,_,_=apply_geometry_resolution(geometry(body),PcbGrid(nm))
                arc=next(r for r in modeled.routes if r.kind=='Arc')
                self.assertEqual(arc.status,'verified')
                with self.assertRaisesRegex(ConfigurationError,'source route Arc unsupported'):
                    extract_trace_sections(modeled)

    def test_semantic_survival_rejects_real_changes(self):
        from antenna_lab.pcb.routes import audit_projected_routes
        from antenna_lab.pcb.model import CopperPolygon
        g,rid=projection_case(1e-5)
        r=next(r for r in g.routes if r.id==rid)
        owner=next(c for c in g.copper if c.id==r.conductor_id)
        cases=[
            ('removed_by_projection',r,[]),
            ('ambiguous_conductor',r,[owner,replace(owner,id='duplicate')]),
            ('ownership_changed',r,[replace(owner,id='changed')]),
            ('collapsed_axis',replace(r,stop_xy_m=r.start_xy_m),[owner]),
            ('collapsed_width',replace(r,width_m=0),[owner]),
            ('centerline_not_preserved',replace(r,stop_xy_m=(.006,0)),[owner]),
            ('centerline_not_preserved',replace(r,start_xy_m=(.0008,0)),[owner]),
        ]
        for status,route,copper in cases:
            with self.subTest(status=status,route=route.start_xy_m):
                actual=audit_projected_routes((route,),copper,(r,))[0]
                self.assertEqual(actual.status,status)
                self.assertIsNone(actual.conductor_id)

    def test_partial_clear_proof_cannot_be_upgraded_by_projection(self):
        from antenna_lab.pcb.routes import audit_projected_routes
        g=geometry(LINE+'%LPC*%\n%ADD11C,0.1*%\nD11*\nX3000000Y90000D03*\n')
        # Even a restored modeled polygon cannot manufacture source evidence.
        intact=geometry(LINE)
        result=audit_projected_routes(g.routes,intact.copper,g.routes)
        self.assertEqual(result[0].status,'stroke_not_preserved')
        g.routes=result;g.copper=intact.copper
        with self.assertRaisesRegex(ConfigurationError,'original=stroke_not_preserved'):
            extract_trace_sections(g)

    def test_physical_topology_failure_still_aborts(self):
        from antenna_lab.pcb.quantization import QuantizationError
        g,_=projection_case(1e-5)
        # A real narrow physical hole collapses, irrespective of route status.
        c=g.copper[0]
        x=-.003
        hole=((x-1e-6,-1e-6),(x+1e-6,-1e-6),(x+1e-6,1e-6),(x-1e-6,1e-6))
        g.copper[0]=replace(c,holes_xy_m=(hole,))
        with self.assertRaises(QuantizationError):apply_geometry_resolution(g,PcbGrid())

    def test_stale_receipt_cannot_authorize_changed_geometry(self):
        g,_=projection_case(1e-5)
        modeled,ticks,_=apply_geometry_resolution(g,PcbGrid())
        modeled.copper[0]=replace(modeled.copper[0],id='changed')
        with self.assertRaisesRegex(ConfigurationError,'stale physical quantization audit'):
            extract_trace_sections(modeled)
        from antenna_lab.pcb.geometry_resolution import materialize_quantized_geometry
        route=ticks.routes[0]
        changed=replace(ticks,routes=(replace(route,width=route.width+1),)+ticks.routes[1:])
        modeled=materialize_quantized_geometry(changed)
        with self.assertRaisesRegex(ConfigurationError,'stale physical quantization audit'):
            extract_trace_sections(modeled)

    def test_synthetic_legacy_extraction_unchanged(self):
        from test_pcb_reduced import case
        g=case();before=g.as_dict()
        self.assertEqual(len(extract_trace_sections(g)[0]),2)
        self.assertEqual(before,g.as_dict())


if __name__=='__main__':unittest.main()
