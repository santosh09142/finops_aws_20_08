from config import SERVICE_MAP

service = "s3"

svc_cls = SERVICE_MAP.get(service)

print(svc_cls)
