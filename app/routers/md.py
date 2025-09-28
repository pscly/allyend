"""
通用参数回显接口：/md

- 支持 GET/POST
- 同时接受 Query 参数、Form 参数、JSON 参数
- 后端直接返回 JSON，前端可作为透明代理
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Request, UploadFile

from ..utils.time_utils import aware_now


router = APIRouter()


async def _extract_params(request: Request) -> Dict[str, Any]:
    """提取并合并 Query / Form / JSON 参数（后者覆盖前者）。

    返回一个普通 dict，文件类型（UploadFile）仅回显文件名。
    """
    # Query 参数（str->str）
    q_params: Dict[str, Any] = dict(request.query_params or {})

    # Form 参数（可能包含文件）
    form_params: Dict[str, Any] = {}
    try:
        form = await request.form()
        # starlette.datastructures.FormData 可直接 dict()，重复键仅保留最后一个
        for k, v in (form or {}).items():
            if isinstance(v, UploadFile):
                form_params[k] = v.filename
            else:
                form_params[k] = v
    except Exception:
        # 非 form 提交或解析失败时忽略
        pass

    # JSON 参数
    json_params: Dict[str, Any] = {}
    try:
        body = await request.json()
        if isinstance(body, dict):
            json_params = body
    except Exception:
        # 非 JSON 提交或解析失败时忽略
        pass

    merged: Dict[str, Any] = {}
    merged.update(q_params)
    merged.update(form_params)
    merged.update(json_params)
    return merged


def _pick_first(*values: Optional[Any]) -> Optional[Any]:
    """返回第一个非空（非 None/非空字符串）的值。"""
    for v in values:
        if v is None:
            continue
        if isinstance(v, str) and v == "":
            continue
        return v
    return None


@router.api_route("/md", methods=["GET", "POST"])
async def md(request: Request) -> Dict[str, Any]:
    """参数回显接口。

    - data: 合并后的参数（query + form + json）
    - laizi/who: 为便于脚本获取，单独抽取常用字段（优先顺序：query -> form -> json）
    - time/time2: 格式化时间与时间戳
    - ip: X-Forwarded-For 首个地址（无则为客户端地址）
    - urls: 原始请求 URL
    """
    params = await _extract_params(request)

    # 单独字段抽取（按示例优先顺序 query -> form -> json）
    laizi = _pick_first(
        request.query_params.get("laizi"),
        (await _safe_form_get(request, "laizi")),
        params.get("laizi"),  # 最后再看合并后的（可能来自 json）
    )
    who = _pick_first(
        request.query_params.get("who"),
        (await _safe_form_get(request, "who")),
        params.get("who"),
    )

    # 时间信息
    now = aware_now()

    # 客户端 IP
    # 在启用 ProxyHeadersMiddleware 后，request.headers.get("X-Real-IP") 已是“可信代理解析后”的结果
    # 仍保留对常见头部的回退解析
    # ip = request.headers.get("X-Real-IP") if request.client else None
    # "test":{
    #     "1":request.headers.get("CF-Connecting-IP"),  # None
    #     "2":request.headers.get("X-Forwarded-For"),   # 140.xxxxx, 140.xxxxx
    #     "3":request.headers.get("X-Real-IP"), # 140.xxxxx
    #     "4":request.headers.get("X-Forwarded-For"),   # 140.xxxxx, 140.xxxxx
    #     "5":request.headers.get("X-client_ip"),   # None
    # },
    ip = request.headers.get("X-Real-IP")
    # if not ip:
    fwd = (
        request.headers.get("CF-Connecting-IP")
        or request.headers.get("X-Real-IP")
        or request.headers.get("X-client_ip")
        or request.headers.get("x-forwarded-for")
    )
    if fwd:
        ip = fwd.split(",")[0].strip()

    return {
        "data": params,

        "laizi": laizi,
        "time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "time2": now.timestamp(),
        "ip": ip,
        "who": who,
        "urls": str(request.url),
    }


async def _safe_form_get(request: Request, key: str) -> Optional[str]:
    """安全获取 form 中的某个键值，失败返回 None。"""
    try:
        form = await request.form()
        return form.get(key)
    except Exception:
        return None
