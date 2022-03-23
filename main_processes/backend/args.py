from nxs_types.nxs_args import NxsBackendArgs


def parse_args():
    from main_processes.common_args import get_common_parser

    parser = get_common_parser()
    parser.add_argument("--backend_name", type=str)
    parser.add_argument(
        "--force_cpu", default=False, type=lambda x: (str(x).lower() == "true")
    )
    _args = parser.parse_args()

    args = NxsBackendArgs(**(vars(_args)))

    return args
