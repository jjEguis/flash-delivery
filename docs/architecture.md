> Documento histórico de fase 1. Para el diseño vigente consultar [arquitectura general](ARQUITECTURA_GENERAL.md) y [especificaciones](specs/README.md). Sus diferencias no deben trasladarse a código sin reconciliación.

# Decisiones de fase 1

Monolito modular serverless. Los ocho módulos son paquetes vacíos. Los contratos de diseño v1 están en [module-contracts.md](module-contracts.md);
los patrones de almacenamiento en [data-access-patterns.md](data-access-patterns.md).
Todavía no existen contratos ejecutables ni módulos conectados. Ningún
módulo debe importar implementaciones internas de otro. `shared` contiene únicamente
configuración, fábricas técnicas y excepciones comunes futuras.

Una tabla con PK/SK y dos GSIs, proyección ALL y facturación bajo demanda.
Redis expone su cliente nativo reutilizable (TTL, sets y sorted sets), sin políticas
ni datos de disponibilidad. No hay Scan ni autenticación ni datos de negocio.

CDK genera CloudFormation con Lambda inline, evitando assets S3, bootstrap y CLI CDK.
Un script boto3 aplica esa plantilla exclusivamente a MiniStack. La Lambda de salud
no necesita permisos de datos. El entorno no admite endpoints AWS públicos ni
credenciales distintas de test; los SDK usan endpoint explícito y no usan proxies.

MiniStack ejecuta la Lambda Python como subproceso dentro de su contenedor. No requiere
montar el socket Docker; esto no reproduce el aislamiento del runtime AWS real.
Redis es el almacén de la aplicación, no ElastiCache ni una dependencia de emulación.
