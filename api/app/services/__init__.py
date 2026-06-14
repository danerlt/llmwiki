# package
# 所有 service 已迁移为"类 + 单例"。在此重导出单例实例，
# 使 `from app.services import X` 拿到单例（调用点写法不变）。
from app.services.activity_service import activity_service
from app.services.analytics_service import analytics_service
from app.services.api_key_service import api_key_service
from app.services.audit_service import audit_service
from app.services.auth_service import auth_service
from app.services.embedding_service import embedding_service
from app.services.ingest_service import ingest_service
from app.services.kb_service import kb_service
from app.services.notification_service import notification_service
from app.services.org_service import org_service
from app.services.permission_service import permission_service
from app.services.promotion_service import promotion_service
from app.services.query_service import query_service
from app.services.retrieval_service import retrieval_service
from app.services.webhook_service import webhook_service

__all__ = [
    "activity_service",
    "analytics_service",
    "api_key_service",
    "audit_service",
    "auth_service",
    "embedding_service",
    "ingest_service",
    "kb_service",
    "notification_service",
    "org_service",
    "permission_service",
    "promotion_service",
    "query_service",
    "retrieval_service",
    "webhook_service",
]
