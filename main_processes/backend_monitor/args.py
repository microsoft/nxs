from nxs_types.nxs_args import NxsBackendMonitorArgs


def parse_args():
    from main_processes.common_args import get_common_parser

    parser = get_common_parser()
    parser.add_argument("--polling_interval_secs", type=float, default=3)
    _args = parser.parse_args()

    args = NxsBackendMonitorArgs(**(vars(_args)))

    return args
