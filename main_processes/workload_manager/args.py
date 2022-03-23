from nxs_types.nxs_args import NxsWorkloadManagerArgs


def parse_args():
    from main_processes.common_args import get_common_parser

    parser = get_common_parser()
    parser.add_argument("--model_timeout_secs", type=float, default=30)
    parser.add_argument("--report_workloads_interval", type=float, default=10)
    parser.add_argument(
        "--enable_instant_scheduling",
        default=False,
        type=lambda x: (str(x).lower() == "true"),
    )
    _args = parser.parse_args()

    args = NxsWorkloadManagerArgs(**(vars(_args)))

    return args
