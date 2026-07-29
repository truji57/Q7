# Q7 - Trading Bot Replicator

Replicacion de bots de trading desde MetaTrader 5 hacia NinjaTrader 8 para operar en mercados de futuros con cuentas de fondeo (prop firms).

## Arquitectura

```
┌─────────────────────┐     ┌──────────────────────────────────┐
│  SIGNAL ENGINE (C#) │────▶│  ACCOUNT MANAGER (Python + C#)   │
│  Estrategia price   │     │  Rotacion cuentas, riesgo, GUI   │
│  action + liquidez  │◀────│                                  │
└─────────────────────┘     └──────────────────────────────────┘
```

**Desacoplados**: el Engine solo dice "entra LONG/SHORT". El Manager decide en que cuenta, cuanto lote, y si toca rotar.

## Estructura

```
Q7/
├── README.md
├── docs/
│   ├── contexto.md
│   ├── analisis-bots.md
│   ├── estrategias.md
│   └── arquitectura-ninjatrader.md
├── Recursos/              # .ex5 y .set originales
└── src/
    ├── Q7NinjaTrader/
    │   ├── Strategies/
    │   │   └── Q7SignalEngine.cs
    │   ├── AddOns/
    │   │   └── Q7AccountManagerAddOn.cs
    │   └── Indicators/
    │       └── Q7StructureAnalyzer.cs
    ├── Q7Orchestrator/
    │   ├── app.py              # Flask + SocketIO dashboard
    │   ├── orchestrator.py      # Logica multi-cuenta
    │   ├── signal_watcher.py    # Lee senales del Engine
    │   ├── config.json          # Config cuentas y riesgo
    │   └── requirements.txt
    └── Q7Dashboard/
        └── templates/
            └── index.html       # Dashboard web
```

## Quick Start

### 1. Instalar componentes NinjaTrader

Copia los archivos `.cs` a las carpetas de NinjaTrader 8:

```
Documents\NinjaTrader 8\bin\Custom\Strategies\Q7SignalEngine.cs
Documents\NinjaTrader 8\bin\Custom\AddOns\Q7AccountManagerAddOn.cs
Documents\NinjaTrader 8\bin\Custom\Indicators\Q7StructureAnalyzer.cs
```

**Requiere `Newtonsoft.Json.dll`** en `Documents\NinjaTrader 8\bin\Custom\`.

Abre NinjaScript Editor → Compile (F5).

### 2. Arrancar Orchestrator + Dashboard

```bash
cd src\Q7Orchestrator
pip install -r requirements.txt
python app.py --config config.json --port 5000
```

### 3. Abrir Dashboard

```
http://127.0.0.1:5000
```

### 4. Flujo de trabajo

1. **Abre un chart** en NT8 con YM u otro futuro
2. **Anade Q7SignalEngine** como estrategia al chart
3. **START** desde el dashboard
4. El Engine publica senales → Orchestrator las recibe
5. Orchestrator decide cuenta y lote → envia comando al AddOn NT8
6. AddOn ejecuta en la cuenta activa → reporta P&L de vuelta
7. Al llegar a target → rota a siguiente cuenta

### 5. Backtesting

El `Q7SignalEngine` se puede probar directamente en el **Strategy Analyzer** de NT8:

- Parameters > Optimize para optimizar `VelasPeriodo`, `SlTicks`, `RiskReward`
- Usar datos historicos de futuros (YM para US30, GC para XAUUSD)

## Configuracion

Editar `src/Q7Orchestrator/config.json`:

```json
{
  "q7": {
    "accounts": [
      {
        "id": 1,
        "name": "Apex PA #12345",
        "daily_profit_target": 1500,
        "daily_loss_limit": 1500,
        "base_contracts": 1
      }
    ],
    "risk": {
      "martingale_multiplier": 1.6,
      "max_consecutive_losses": 5
    }
  }
}
```

## Componentes

| Componente | Archivo | Tecnologia | Funcion |
|------------|---------|------------|---------|
| Signal Engine | `Q7SignalEngine.cs` | C# NinjaScript | Detecta liquidity sweeps, publica senales |
| Structure Analyzer | `Q7StructureAnalyzer.cs` | C# NinjaScript | Swing points + tendencia |
| Account Manager | `Q7AccountManagerAddOn.cs` | C# NinjaScript | Ejecuta en NT8, reporta P&L |
| Orchestrator | `orchestrator.py` | Python | Logica multi-cuenta, rotacion, riesgo |
| Signal Watcher | `signal_watcher.py` | Python | Lee signals/ y enruta al Orchestrator |
| Dashboard | `app.py` + `index.html` | Flask + SocketIO | GUI web tiempo real |
