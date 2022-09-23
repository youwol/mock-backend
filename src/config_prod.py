import os

from youwol_mock_backend import Configuration
from youwol_utils import RedisCacheClient, CleanerThread
from youwol_utils.clients.oidc.oidc_config import PrivateClient, OidcInfos
from youwol_utils.context import DeployedContextReporter
from youwol_utils.middlewares import AuthMiddleware
from youwol_utils.middlewares import JwtProviderCookie, JwtProviderBearer
from youwol_utils.servers.env import REDIS, KEYCLOAK_ADMIN, OPENID_CLIENT, Env
from youwol_utils.servers.fast_api import AppConfiguration, ServerOptions, FastApiMiddleware


async def get_configuration():
    required_env_vars = OPENID_CLIENT + REDIS + KEYCLOAK_ADMIN

    not_founds = [v for v in required_env_vars if not os.getenv(v)]
    if not_founds:
        raise RuntimeError(f"Missing environments variable: {not_founds}")

    openid_base_url = os.getenv(Env.OPENID_BASE_URL)
    openid_client_id = os.getenv(Env.OPENID_CLIENT_ID)
    openid_client_secret = os.getenv(Env.OPENID_CLIENT_SECRET)
    openid_infos = OidcInfos(base_uri=openid_base_url,
                             client=PrivateClient(
                                 client_id=openid_client_id,
                                 client_secret=openid_client_secret)
                             )

    redis_host = os.getenv(Env.REDIS_HOST)
    jwt_cache = RedisCacheClient(host=redis_host, prefix='jwt_cache')

    cleaner_thread = CleanerThread()

    async def on_before_startup():
        try:
            cleaner_thread.go()
        except BaseException as e:
            print("Error while starting download thread")
            raise e

    service_config = Configuration()

    server_options = ServerOptions(
        root_path='/api/mock_backend',
        http_port=8080,
        base_path="",
        middlewares=[
            FastApiMiddleware(
                AuthMiddleware, {
                    'openid_infos': openid_infos,
                    'predicate_public_path': lambda url:
                    url.path.endswith("/healthz") or url.path.startswith("/api/mock_backend/pub/"),
                    'jwt_providers': [JwtProviderBearer(),
                                      JwtProviderCookie(
                                          jwt_cache=jwt_cache,
                                          openid_infos=openid_infos
                                      )],
                }
            )

        ],
        ctx_logger=DeployedContextReporter(),
        on_before_startup=on_before_startup
    )
    return AppConfiguration(
        server=server_options,
        service=service_config
    )
