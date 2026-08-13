# Diagrama de Limites Q7

## Jerarquia de Limites

```
┌─────────────────────────────────────────────────────────────┐
│                    TPG/SLG (GLOBAL)                         │
│                    PNL Total acumulado                       │
│                    Desactiva cuenta permanentemente          │
│                    Prioridad MAXIMA                          │
├─────────────────────────────────────────────────────────────┤
│                    TPxR/SLxR (RONDA)                        │
│                    PNL Ronda acumulado                       │
│                    Desactiva cuenta en la ronda              │
│                    Prioridad MEDIA                           │
├─────────────────────────────────────────────────────────────┤
│                    TPC/SLC (CICLO)                           │
│                    PnL de la posicion actual                 │
│                    Cierra la posicion                        │
│                    Prioridad MINIMA                          │
└─────────────────────────────────────────────────────────────┘
```

## Flujo de Evaluacion (en cada sync)

```
Senal de MT5 recibida
        │
        ▼
┌─────────────────┐
│ Abrir posicion  │
│ (Ciclo inicia)  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    SYNC (cada 200ms)                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. TPG/SLG (Global) - PRIORIDAD MAXIMA                     │
│     ┌─────────────────────────────────────────────────────┐ │
│     │ PNL Total >= TPG? ──→ TP_GLOBAL ──→ Desactivar     │ │
│     │ PNL Total <= -SLG? ──→ SL_GLOBAL ──→ Desactivar    │ │
│     └─────────────────────────────────────────────────────┘ │
│                                                             │
│  2. TPxR/SLxR (Ronda) - PRIORIDAD MEDIA                     │
│     ┌─────────────────────────────────────────────────────┐ │
│     │ PNL Ronda >= TPxR? ──→ TP_RONDA ──→ Desactivar     │ │
│     │ PNL Ronda <= -SLxR? ──→ SL_RONDA ──→ Desactivar    │ │
│     └─────────────────────────────────────────────────────┘ │
│                                                             │
│  3. TPC/SLC (Ciclo) - PRIORIDAD MINIMA                      │
│     ┌─────────────────────────────────────────────────────┐ │
│     │ PnL Ciclo >= TPC? ──→ TP_CICLO ──→ Cerrar posicion │ │
│     │ PnL Ciclo <= -SLC? ──→ SL_CICLO ──→ Cerrar posicion│ │
│     └─────────────────────────────────────────────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Ejemplo Practico

### Configuracion
```
Cuenta: Sim101
INI: $50,000
CT: 10 contratos
TPC: $500   (Take Profit por Ciclo)
SLC: $1000  (Stop Loss por Ciclo)
TPxR: $1500 (Take Profit por Ronda)
SLxR: $2000 (Stop Loss por Ronda)
TPG: $3050  (Take Profit Global)
SLG: $2000  (Stop Loss Global)
Modo: Diario
```

### Escenario 1: Ciclo normal
```
Sim101 abre LONG 10 contratos
        │
        ▼
PnL de la posicion = +$500
        │
        ▼
TPC alcanzado → Cerrar posicion
        │
        ▼
Siguiente cuenta (Sim102)
```

### Escenario 2: Ronda completada
```
Sim101 ha acumulado +$1500 en PNL Ronda
        │
        ▼
TPxR alcanzado → Desactivar Sim101
        │
        ▼
Siguiente cuenta (Sim102)
```

### Escenario 3: Limite Global alcanzado
```
Sim101 ha acumulado +$3050 en PNL Total
(desde el inicio de la cuenta)
        │
        ▼
TPG alcanzado → Desactivar Sim101 permanentemente
        │
        ▼
Siguiente cuenta (Sim102)
```

### Escenario 4: RESET
```
Usuario hace RESET en el grupo
        │
        ▼
Re-habilitar todas las cuentas
        │
        ▼
Re-evaluar TPG/SLG:
  - Sim101: PNL Total = $3050, TPG = $3050 → Desactivar
  - Sim102: PNL Total = $0, TPG = $3050 → Habilitar
  - Sim103: PNL Total = $0, TPG = $3050 → Habilitar
  - Sim104: PNL Total = $0, TPG = $3050 → Habilitar
  - Sim105: PNL Total = $0, TPG = $3050 → Habilitar
        │
        ▼
Empieza desde Sim102 (primera habilitada)
```

## Modos de Reinicio

### Manual
```
Ronda completada → Grupo se desactiva
        │
        ▼
RESET manual → Re-habilitar y re-evaluar
```

### Diario
```
Ronda completada → Grupo se desactiva
        │
        ▼
00:00 → Reset automatico de cuentas
```

### Continuo
```
Ronda completada → Reset automatico
        │
        ▼
Nueva ronda inicia automaticamente
```

## Metricas de PnL

```
PNL DIA = Gross Realized PnL + Unrealized (desde NT8)
        │
        └─→ Se resetea a las 00:00

PNL RONDA = (Realized - Round Start Realized) + Unrealized
        │
        └─→ Se resetea al inicio de cada ronda

PNL TOTAL = (Balance + Unrealized) - Starting Balance (INI)
        │
        └─→ Se resetea solo al hacer RESET

OPEN = Unrealized PnL (flotante)
        │
        └─→ Informativo, se actualiza en tiempo real
```

## Parametros de Configuracion

| Parametro | Descripcion | Ejemplo |
|-----------|-------------|---------|
| **CT** | Contratos por operacion | 10 |
| **MXP** | Maximo de posiciones simultaneas | 6 |
| **TPC** | Take Profit por Ciclo | $500 |
| **SLC** | Stop Loss por Ciclo | $1000 |
| **TPxR** | Take Profit por Ronda | $1500 |
| **SLxR** | Stop Loss por Ronda | $2000 |
| **TPG** | Take Profit Global | $3050 |
| **SLG** | Stop Loss Global | $2000 |

## Prioridades Resumidas

```
TPG/SLG > TPxR/SLxR > TPC/SLC

Global > Ronda > Ciclo
```
