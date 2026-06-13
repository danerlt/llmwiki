"""极简进程内指标，按 Prometheus 文本曝光格式输出，供 /metrics 抓取。

不引入额外依赖；多实例部署时各进程独立计数（由 Prometheus 按实例聚合）。
"""

import threading

_lock = threading.Lock()
_req_total: dict[tuple[str, str], int] = {}
_dur_sum: float = 0.0
_dur_count: int = 0
_llm_calls: int = 0
_llm_tokens: int = 0


def observe(method: str, status: int, dur_s: float) -> None:
    global _dur_sum, _dur_count
    with _lock:
        key = (method, str(status))
        _req_total[key] = _req_total.get(key, 0) + 1
        _dur_sum += dur_s
        _dur_count += 1


def observe_llm(tokens: int = 0) -> None:
    """记录一次 LLM 调用及其 token 用量（成本可观测）。"""
    global _llm_calls, _llm_tokens
    with _lock:
        _llm_calls += 1
        _llm_tokens += max(0, int(tokens))


def render() -> str:
    lines = [
        "# HELP http_requests_total Total HTTP requests by method and status.",
        "# TYPE http_requests_total counter",
    ]
    with _lock:
        for (method, status), n in sorted(_req_total.items()):
            lines.append(f'http_requests_total{{method="{method}",status="{status}"}} {n}')
        lines.append("# HELP http_request_duration_seconds Aggregate request duration.")
        lines.append("# TYPE http_request_duration_seconds summary")
        lines.append(f"http_request_duration_seconds_sum {_dur_sum}")
        lines.append(f"http_request_duration_seconds_count {_dur_count}")
        lines.append("# HELP llm_calls_total Total upstream LLM calls.")
        lines.append("# TYPE llm_calls_total counter")
        lines.append(f"llm_calls_total {_llm_calls}")
        lines.append("# HELP llm_tokens_total Total LLM tokens consumed.")
        lines.append("# TYPE llm_tokens_total counter")
        lines.append(f"llm_tokens_total {_llm_tokens}")
    return "\n".join(lines) + "\n"
