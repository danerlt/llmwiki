"""业务异常树 + 错误码。

控制器/服务抛 AppException 子类，由 register_exception 统一转成"对应 HTTP 状态码 + 信封"。
错误码当前与 HTTP 状态码同值（字符串），后续可细化为业务子码而不破坏前端拆包契约。
"""
from enum import Enum


class ErrorCode(str, Enum):
    SUCCESS = "0"
    BAD_REQUEST = "400"
    UNAUTHORIZED = "401"
    FORBIDDEN = "403"
    NOT_FOUND = "404"
    CONFLICT = "409"
    UNPROCESSABLE = "422"
    INTERNAL = "500"


class AppException(Exception):
    """所有业务异常的基类。子类用类属性声明默认 code/http_status/message。"""

    code: ErrorCode = ErrorCode.INTERNAL
    http_status: int = 500
    default_message: str = "服务内部错误"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: ErrorCode | None = None,
        http_status: int | None = None,
    ) -> None:
        self.message = message or self.default_message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        super().__init__(self.message)


class BadRequestException(AppException):
    code = ErrorCode.BAD_REQUEST
    http_status = 400
    default_message = "请求参数错误"


class ParamsException(BadRequestException):
    """参数/校验类错误（语义上等同 BadRequest，便于服务层表达意图）。"""


class UnauthorizedException(AppException):
    code = ErrorCode.UNAUTHORIZED
    http_status = 401
    default_message = "未认证或登录已过期"


class ForbiddenException(AppException):
    code = ErrorCode.FORBIDDEN
    http_status = 403
    default_message = "无权访问"


class NotFoundException(AppException):
    code = ErrorCode.NOT_FOUND
    http_status = 404
    default_message = "资源不存在"


class ConflictException(AppException):
    code = ErrorCode.CONFLICT
    http_status = 409
    default_message = "资源冲突"


class DBException(AppException):
    code = ErrorCode.INTERNAL
    http_status = 500
    default_message = "数据库操作失败"
