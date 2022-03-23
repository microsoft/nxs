from nxs_types.nxs_args import NxsApiArgs


def parse_args():
    from main_processes.common_args import get_common_parser

    parser = get_common_parser()
    parser.add_argument("--frontend_name", type=str, default="test_frontend")
    parser.add_argument("--port", type=int, default=8888)
    parser.add_argument("--workload_report_period_secs", type=float, default=1)
    parser.add_argument("--model_caching_timeout_secs", type=float, default=1)
    parser.add_argument("--api_key", type=str, default="")
    parser.add_argument(
        "--enable_benchmark_api",
        default=False,
        type=lambda x: (str(x).lower() == "true"),
    )
    parser.add_argument(
        "--enable_v1_api",
        default=False,
        type=lambda x: (str(x).lower() == "true"),
    )
    _args = parser.parse_args()

    args = NxsApiArgs(**(vars(_args)))

    return args
