# Arquitectura Q7 - NinjaTrader 8

## Principio: Separacion de Responsabilidades

El sistema se divide en **2 modulos independientes** que se comunican por un contrato bien definido:

```
┌─────────────────────┐              ┌──────────────────────────────────┐
│  Q7 SIGNAL ENGINE   │   señales   │  Q7 ACCOUNT MANAGER (Sistema)    │
│  (Estrategia)       │ ──────────► │                                  │
│                     │              │  ┌─────────────────────────┐     │
│  - Price action     │◄─────────── │  │  DASHBOARD WEB (React)   │     │
│  - Estructura       │   estado    │  │  - Estado N cuentas      │     │
│  - Liquidez         │             │  │  - P&L, target, DD       │     │
│  - SL/TP fijo       │             │  │  - Logs, controles       │     │
│                     │              │  └───────────┬─────────────┘     │
│  ESTO SE CAMBIA     │              │              │ WebSocket         │
│  PARA PROBAR        │              │  ┌───────────▼─────────────┐     │
│  OTRAS ESTRATEGIAS  │              │  │  BACKEND PYTHON          │     │
│                     │              │  │  (Flask + SocketIO)      │     │
│  Params:            │              │  │  - Orquestador           │     │
│  - velas_periodo    │              │  │  - Rotacion cuentas      │     │
│  - sl_pips          │              │  │  - Control riesgo global │     │
│  - riskreward       │              │  └───────────┬─────────────┘     │
│  - aleatoriedad     │              │              │ ATI (files .txt)  │
└─────────────────────┘              │  ┌───────────▼─────────────┐     │
                                     │  │  NINJATRADER ADDON (C#) │     │
                                     │  │  - Ejecuta en N cuentas │     │
                                     │  │  - Reporta P&L y estado │     │
                                     │  │  - Recibe comandos      │     │
                                     │  └─────────────────────────┘     │
                                     │                                  │
                                     │  ESTO NO SE TOCA                 │
                                     └──────────────────────────────────┘
```

## Contrato de Comunicacion entre Modulos

La interfaz es un **JSON estandar** que viaja por archivos ATI o WebSocket local:

### Señal (Engine → Manager)

```json
// signal.json
{
  "type": "SIGNAL",
  "timestamp": "2026-07-23T14:35:00Z",
  "action": "ENTER_LONG",
  "account_filter": {
    "id": null,
    "only_if_target_not_reached": true
  },
  "order": {
    "instrument": "YM 09-26",
    "sl_ticks": 75,
    "tp_ticks": 90,
    "rr_ratio": 1.2
  }
}
```

### Estado (Manager → Engine)

```json
// state.json
{
  "type": "STATE",
  "timestamp": "2026-07-23T14:35:01Z",
  "active_account": {
    "id": 3,
    "balance": 98500.00,
    "daily_pnl": 1200.00,
    "daily_target_reached": false,
    "daily_loss_reached": false,
    "contract_size": 2,
    "description": "Apex PA #50123456"
  },
  "all_accounts": [
    { "id": 1, "status": "TARGET_REACHED", "daily_pnl": 1500.00 },
    { "id": 2, "status": "TARGET_REACHED", "daily_pnl": 1600.00 },
    { "id": 3, "status": "TRADING", "daily_pnl": 1200.00 },
    { "id": 4, "status": "PENDING", "daily_pnl": 0.00 },
    { "id": 5, "status": "PENDING", "daily_pnl": 0.00 }
  ],
  "risk": {
    "martingale_active": true,
    "multiplier": 1.6,
    "consecutive_losses": 0
  }
}
```

### Comando (Manager → Engine)

```json
// command.json
{
  "type": "COMMAND",
  "command": "START" | "STOP" | "PAUSE" | "SKIP_ACCOUNT"
}
```

## Modulo 1: Q7 Signal Engine (Estrategia)

### Ubicacion en el proyecto

```
Q7/
├── src/
│   ├── Q7SignalEngine/              # Motor de señales (la estrategia pura)
│   │   ├── Q7Strategy.cs            # Clase NinjaScript Strategy
│   │   ├── Indicators/
│   │   │   └── Q7StructureAnalyzer.cs  # Swing points + liquidez
│   │   ├── Signals/
│   │   │   ├── ILiquiditySweepDetector.cs  # Interfaz de patron de entrada
│   │   │   ├── LiquiditySweepV1.cs         # Implementacion liquidity sweep
│   │   │   └── BreakoutV1.cs              # Futura: otra estrategia
│   │   ├── Q7SessionFilter.cs        # Filtro horario
│   │   └── Q7SignalPublisher.cs      # Publica la señal JSON (ATI/WS)
│   │
│   └── Q7AccountManager/            # Gestor multi-cuenta (el sistema)
│       ├── Q7WebDashboard/           # Frontend React/Vue
│       ├── Q7Orchestrator/           # Backend Python
│       └── Q7NinjaAddon/             # AddOn C# en NinjaTrader
```

### Responsabilidades del Signal Engine

- NO sabe cuantas cuentas hay
- NO sabe que cuenta esta activa
- NO hace seguimiento de P&L global
- NO decide cuanto lote usar (eso lo decide el Manager en base al riesgo)
- SOLO dice: "entra LONG ahora con SL=X y TP=Y"
- SOLO recibe un comando: "START / STOP / PAUSE"

```csharp
// Q7Strategy.cs (resumen)
public class Q7Strategy : Strategy
{
    // --- PARAMETROS CONFIGURABLES ---
    private int velasPeriodo = 20;
    private int slTicks = 75;
    private double riskReward = 1.2;
    
    private Q7StructureAnalyzer analyzer;
    private Q7SessionFilter sessionFilter;
    private Q7SignalPublisher publisher;
    
    protected override void OnBarUpdate()
    {
        // 1. Filtro sesion
        if (!sessionFilter.IsTradingAllowed(Time[0])) return;
        
        // 2. Analizar estructura
        var structure = analyzer.Analyze(High, Low, Close, velasPeriodo);
        
        // 3. Detectar liquidity sweep
        bool signalLong = LiquiditySweepV1.DetectLong(structure, Close, Low);
        bool signalShort = LiquiditySweepV1.DetectShort(structure, Close, High);
        
        // 4. Publicar señal
        if (signalLong)
            publisher.SendSignal("ENTER_LONG", slTicks, (int)(slTicks * riskReward));
        else if (signalShort)
            publisher.SendSignal("ENTER_SHORT", slTicks, (int)(slTicks * riskReward));
    }
}
```

---

## Modulo 2: Q7 Account Manager (Sistema)

### 2.1 NinjaTrader AddOn (C#)

Componente dentro de NT8 que se conecta a N cuentas. Usa la API de Account de NT8 para ejecutar ordenes y leer balances.

```csharp
// Q7AccountManager.cs
public class Q7AccountManager : AddOnBase
{
    private List<Account> accounts = new();
    private Account activeAccount;
    private int currentAccountIndex = 0;
    
    // Leer señales de Q7SignalEngine (por ATI o por cola compartida)
    // Ejecutar ENTER_LONG/SHORT solo en la cuenta activa
    
    // Tras cada operacion:
    //   - Si daily_profit >= target → marcar TARGET_REACHED, rotar a siguiente
    //   - Si daily_loss >= limit → marcar LOSS_LIMIT, rotar a siguiente
    
    // Al rotar:
    //   - currentAccountIndex++
    //   - Si todas alcanzaron target → todas a PENDING para siguiente dia
}
```

### 2.2 Backend Python (Orquestador)

```python
# orchestrator.py
class Q7Orchestrator:
    def __init__(self):
        self.accounts = []      # Lista de cuentas configuradas
        self.active_index = 0   # Indice de cuenta activa
        self.martingale = 1.0   # Multiplicador actual
    
    def on_signal(self, signal):
        """Recibe señal del Engine, decide si ejecutar"""
        active = self.accounts[self.active_index]
        
        if active.daily_target_reached or active.daily_loss_reached:
            self.rotate_account()
            active = self.accounts[self.active_index]
        
        order = self.build_order(signal, active)
        self.send_to_ninja(order)
    
    def rotate_account(self):
        self.active_index = (self.active_index + 1) % len(self.accounts)
        # Si todas llegaron a target → esperar al reset diario
        
    def on_trade_closed(self, trade_result):
        if trade_result.profit < 0:
            self.martingale *= 1.6
        else:
            self.martingale = 1.0
```

### 2.3 Dashboard Web (React/Vue)

```
┌──────────────────────────────────────────────────────────┐
│  Q7 Dashboard                           [START] [STOP]   │
├──────────┬──────────┬──────────┬──────────┬──────────────┤
│ Cuenta 1 │ Cuenta 2 │ Cuenta 3 │ Cuenta 4 │ Cuenta 5     │
│ ● ACTIVE │ ● TARGET │ ● TARGET │ ○ PEND   │ ○ PEND       │
│ P&L: +3% │ P&L: +6% │ P&L: +5% │ P&L: 0%  │ P&L: 0%      │
│ DD:  -1% │ DD:  -2% │ DD:   0% │ DD:  0%  │ DD:  0%      │
│ [SKIP]   │          │          │          │              │
├──────────┴──────────┴──────────┴──────────┴──────────────┤
│ Log: [14:35] Señal LONG → Cuenta 1 | YM 43210 | SL 43135 │
│      [14:38] TP alcanzado +$450                           │
│      [14:38] Cuenta 1 → TARGET REACHED → rotando a Cta 4  │
└──────────────────────────────────────────────────────────┘
```

---

## Flujo Completo de una Operacion

```
1. [Signal Engine]   Detecta liquidity sweep LONG en YM
2. [Signal Engine]   Publica: {action: "ENTER_LONG", sl: 75, tp: 90}
3. [Orchestrator]    Recibe, mira: cuenta 3 esta activa, no ha llegado a target
4. [Orchestrator]    Calcula: lote = base * 1.0 (no hay martingala activa)
5. [Orchestrator]    Envia orden al AddOn de Ninja
6. [Ninja AddOn]     Ejecuta EnterLong() en la cuenta 3
7. [Ninja AddOn]     Monitoriza: P&L unrealized de cuenta 3
8. [Ninja AddOn]     SL alcanzado → cierra operacion, reporta al Orchestrator
9. [Orchestrator]    Registra pérdida, activa martingala (×1.6 para siguiente)
10. [Orchestrator]   P&L diario cuenta 3 = -$200 → no llega a loss limit → sigue
11. [Dashboard Web]  Actualiza UI en tiempo real via WebSocket
```

---

## Ventajas de esta Separacion

| Situacion | Que cambias |
|-----------|------------|
| Probar otro patron de entrada | Solo `Q7SignalEngine/Signals/` |
| Anadir trailing stop | Solo `Q7SignalEngine/Q7Strategy.cs` |
| Cambiar de 5 a 10 cuentas | Solo config en `Orchestrator` |
| Cambiar reglas de rotacion | Solo `Orchestrator.on_trade_closed()` |
| Cambiar dashboard | Solo frontend React |
| Reoptimizar parametros | Solo parameter list en `Q7Strategy` |
