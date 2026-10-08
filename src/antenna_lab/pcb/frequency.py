"""Shared PCB CLI frequency units, independent of native/full-wave adapters."""

def add_frequency_arguments(parser):
    parser.add_argument('--center-mhz', type=float, default=1420.)
    parser.add_argument('--cutoff-mhz', type=float, default=200.)
    parser.add_argument('--frequencies-mhz', type=float, nargs='+', default=[1300., 1420., 1500.])
    parser.add_argument('--loss-reference-mhz', type=float)


def frequency_arguments_hz(args):
    # MHz exists only at this command-line boundary; all downstream values are Hz.
    return dict(excitation_center_hz=args.center_mhz*1e6,
                excitation_cutoff_hz=args.cutoff_mhz*1e6,
                result_frequency_hz=tuple(f*1e6 for f in args.frequencies_mhz),
                loss_reference_frequency_hz=(args.center_mhz if args.loss_reference_mhz is None
                                             else args.loss_reference_mhz)*1e6)

