# Contexto del Proyecto Q7

## Problema

Existen bots de trading (Expert Advisors) para MetaTrader 5 que son efectivos para **pasar cuentas de fondeo** (challenges de prop firms). Sin embargo, estos EAs solo funcionan en MT5, que opera principalmente en el mercado **Forex/CFD**.

El objetivo es migrar esta lógica a **NinjaTrader 8** para poder operar en el mercado de **futuros** (CME, CBOT, NYMEX).

## Por qué NinjaTrader + Futuros

| Aspecto | MT5 (Forex/CFD) | NinjaTrader (Futuros) |
|---------|-----------------|----------------------|
| Regulación | Broker-dependent | Mercado centralizado (CME) |
| Transparencia | Spread variable | Order book real |
| Comisiones | Incluidas en spread | Explícitas y fijas |
| Capital requerido | Bajo (forex) | Más alto pero apalancado |
| Prop firms | MFF, FTMO, etc. | Topstep, Apex, etc. |

## Mapeo de Instrumentos

| MT5 (CFD) | NinjaTrader (Futuros) | Símbolo NT |
|-----------|----------------------|------------|
| US30 (Dow Jones) | E-mini Dow | YM |
| US30 (Dow Jones) | Micro E-mini Dow | MYM |
| XAUUSD (Oro) | Gold Futures | GC |
| XAUUSD (Oro) | Micro Gold | MGC |
| GBPUSD | 6B (British Pound) | 6B |

## Prop Firms de Futuros

- **Topstep** - Reglas: Profit target, daily loss limit, trailing drawdown
- **Apex Trader Funding** - Similar estructura
- **Bulenox** - Similar estructura
- **Leeloo** - Similar estructura

## Objetivos del Proyecto

1. **Extraer lógica** de los EAs originales (parámetros .set + decompilación .ex5)
2. **Reimplementar** la estrategia como un NinjaScript Strategy/Indicator
3. **Adaptar** la gestión de riesgo a reglas de prop firms de futuros
4. **Optimizar** parámetros para los instrumentos de futuros equivalentes
5. **Validar** mediante backtesting en NinjaTrader

## Alcance

- **Fase 1**: Análisis y documentación de bots originales
- **Fase 2**: Implementación de la estrategia core en NinjaTrader
- **Fase 3**: Módulo de gestión de riesgo (daily loss, profit target, trailing DD)
- **Fase 4**: Backtesting y optimización por instrumento
- **Fase 5**: Pruebas en sim / cuentas de fondeo reales
