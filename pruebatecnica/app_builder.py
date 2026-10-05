"""Construye todos los stacks de la solución; separado de app.py para poder probarlo."""

import aws_cdk as cdk

from pruebatecnica.config import AppConfig
from pruebatecnica.constructs.nag import acknowledge_cdk_internals
from pruebatecnica.stacks.agents_stack import AgentsStack
from pruebatecnica.stacks.api_stack import ApiStack
from pruebatecnica.stacks.auth_stack import AuthStack
from pruebatecnica.stacks.evaluation_stack import EvaluationStack
from pruebatecnica.stacks.knowledge_stack import KnowledgeStack
from pruebatecnica.stacks.observability_stack import ObservabilityStack
from pruebatecnica.stacks.web_content_stack import WebContentStack
from pruebatecnica.stacks.web_hosting_stack import WebHostingStack


def build_app(app: cdk.App, config: AppConfig) -> dict[str, cdk.Stack]:
    # Las etiquetas se propagan a todo recurso que las admita; el visor de logs filtra por ellas.
    for key, value in config.tags.items():
        cdk.Tags.of(app).add(key, value)

    env = cdk.Environment(account=config.account, region=config.region)
    prefix = "".join(part.capitalize() for part in config.project_name.split("-"))

    def name(domain: str) -> str:
        return f"{prefix}-{domain}"

    observability = ObservabilityStack(app, name("Observability"), config=config, env=env)
    web_hosting = WebHostingStack(
        app, name("WebHosting"), config=config, access_logs_bucket=observability.access_logs_bucket, env=env
    )
    auth = AuthStack(app, name("Auth"), config=config, site_url=web_hosting.site_url, env=env)
    knowledge = KnowledgeStack(
        app,
        name("Knowledge"),
        config=config,
        site_url=web_hosting.site_url,
        access_logs_bucket=observability.access_logs_bucket,
        env=env,
    )
    agents = AgentsStack(app, name("Agents"), config=config, knowledge_base=knowledge.knowledge_base, env=env)
    evaluation = EvaluationStack(app, name("Evaluation"), config=config, agents=agents, env=env)
    api = ApiStack(
        app,
        name("Api"),
        config=config,
        site_url=web_hosting.site_url,
        user_pool=auth.user_pool,
        knowledge=knowledge,
        agents=agents,
        evaluation=evaluation,
        env=env,
    )
    web_content = WebContentStack(
        app,
        name("WebContent"),
        config=config,
        distribution=web_hosting.distribution,
        runtime_config={
            "region": config.region,
            "apiUrl": api.api.url,
            "userPoolId": auth.user_pool.user_pool_id,
            "userPoolClientId": auth.client.user_pool_client_id,
            "cognitoDomain": auth.hosted_ui_domain,
        },
        env=env,
    )

    stacks = {
        "observability": observability,
        "web_hosting": web_hosting,
        "auth": auth,
        "knowledge": knowledge,
        "agents": agents,
        "evaluation": evaluation,
        "api": api,
        "web_content": web_content,
    }
    for stack in stacks.values():
        acknowledge_cdk_internals(stack)
    return stacks
