from nxs_types.nxs_args import NxsSchedulerArgs


def parse_args():
    from main_processes.common_args import get_common_parser

    parser = get_common_parser()
    parser.add_argument("--heartbeat_interval", type=float, default=3)
    parser.add_argument("--model_timeout_secs", type=float, default=180)
    parser.add_argument("--backend_timeout_secs", type=float, default=30)
    parser.add_argument("--epoch_scheduling_interval_secs", type=float, default=10)
    parser.add_argument(
        "--enable_multi_models",
        default=False,
        type=lambda x: (str(x).lower() == "true"),
    )
    parser.add_argument(
        "--enable_instant_scheduling",
        default=False,
        type=lambda x: (str(x).lower() == "true"),
    )
    _args = parser.parse_args()

    args = NxsSchedulerArgs(**(vars(_args)))

    return args
