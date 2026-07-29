# Estrategias de Trading Extraídas

## Estructura Común de Parámetros

Todos los EAs comparten una estructura de parámetros similar dividida en módulos:

### 1. Identificación
```
input_magic_number    → Magic number para identificar órdenes del EA
max_perdidas_consecutivas → Límite de pérdidas seguidas antes de detener
input_activar_horarios    → Flag para filtrar por sesiones de trading
```

### 2. Gestión de Riesgo
```
input_balance_inicial_cuenta → Balance de referencia (normalmente 100,000)
input_maxima_ganancia_diaria  → Límite de profit diario (en % o $)
input_maxima_perdida_diaria   → Límite de pérdida diaria (en % o $)
input_maxima_perdida_cuenta   → Límite de pérdida total de cuenta (%)
input_maxima_perdida_semanal  → Límite de pérdida semanal (%)
```

### 3. Configuración Operativa
```
input_timeframe           → Timeframe de operación (M1=1, M5=5)
input_velas_periodo       → Número de velas para análisis de tendencia
input_porcentaje_riesgo   → % de riesgo por operación
input_RiskReward          → Ratio riesgo/beneficio
input_sl_pips             → Stop Loss en pips/points
input_multiplicador_lotsize → Factor de martingala/anti-martingala
```

### 4. Sesiones de Trading (Horarios)
```
input_operativa_newyork   → Activar sesión NY (bool)
input_ny_desde_hora       → Hora inicio NY (GMT+?)
input_ny_hasta_hora       → Hora fin NY
input_operativa_londres   → Activar sesión Londres (bool)
input_londres_desde_hora  → Hora inicio Londres
input_londres_hasta_hora  → Hora fin Londres
input_operativa_asia      → Activar sesión Asia (bool)
input_asia_desde_hora     → Hora inicio Asia
input_asia_hasta_hora     → Hora fin Asia
input_cerrar_viernes      → Cerrar operaciones antes del fin de semana
gmtofset / gmt_broker     → Offset GMT del broker
```

---

## Parámetros por Estrategia

### BFunded EA - US30 M5
```
Magic: 123456
Balance inicial: 100,000
Max ganancia diaria: 30
Max pérdida diaria: 30
Max pérdida cuenta: 10%
Max pérdida semanal: 10%
Timeframe: M5
Velas periodo: 20
Riesgo: 1.0%
RR: 1.2
SL: 4000 pips
Multiplicador lote: 1.6
Sesiones: NY (7-14) + Londres (3-11)
```

### BFunded EA - US30 M1 (Optimizado)
```
Magic: 123456
Balance inicial: 10,000
Max ganancia diaria: 3% (300)
Max pérdida diaria: 1% (100)
Max pérdida cuenta: 10%
Velas periodo: 19
Timeframe: M1
Riesgo: 0.5%
RR: 1.8
SL: 4400 pips
Multiplicador lote: 2.0
Horarios: Desactivados
Max pérdidas consecutivas: 3
```

### BFunded EA - XAUUSD M5
```
Magic: 42342
Balance inicial: 100,000
Max ganancia diaria: 99 (ilimitado)
Max pérdida diaria: 15
Max pérdida cuenta: 15%
Max pérdida semanal: 99 (ilimitado)
Timeframe: M5
Velas periodo: 10
Riesgo: 0.3%
RR: 1.1
SL: 510 pips
Multiplicador lote: 1.2
Sesiones: NY (7-14) + Londres (3-11)
```

### BFunded EA - GBPUSD M5
```
Magic: 42342
Balance inicial: 100,000
Max ganancia diaria: 10%
Max pérdida diaria: 8%
Max pérdida cuenta: 10%
Max pérdida semanal: 10%
Max pérdidas consecutivas: 3
Timeframe: M5
Velas periodo: 10
Riesgo: 0.7%
RR: 1.1
SL: 120 pips
Multiplicador lote: 1.5
Sesiones: NY (7-14) + Londres (3-11)
```

### ALG Funded - US30 M5
```
Magic: 31231
Max pérdidas consecutivas: 5
Horarios: Desactivados
Balance inicial: 100,000
Max ganancia diaria: 30
Max pérdida diaria: 30
Max pérdida cuenta: 10%
Max pérdida semanal: 10%
Timeframe: M5
Velas periodo: 20
Riesgo: 1.0%
RR: 1.2
SL: 3500 pips
Multiplicador lote: 1.6
Sesiones: NY (7-14) + Londres (3-11)
GMT Broker: +3
```

---

## Información Oficial de los Desarrolladores

### BFunded EA (bfunded.co / thetradingapi.com)

Según la web oficial de BFUNDED:

> *"El EA analiza **estructuras, liquidez y comportamiento previo del precio** para encontrar patrones de alta probabilidad."*

> *"**No usa indicadores tradicionales** y se basa en lógica de **price action**."*

> *"Análisis de precio basado en **algoritmos de price action avanzados**, sin indicadores, identificando patrones de alta probabilidad."*

> *"Construido por **IA**: Nuestro equipo de desarrollo usó la IA para impulsar el motor de decisiones del EA."*

> *"Opera con una **aleatoriedad no predecible**, pero que es capaz de generar operaciones exitosas gracias a su potente algoritmo de análisis de estructuras de mercado."*

> *"BFUNDED EA está desarrollado y patentado por **The Trading API**."*

**Puntos clave extraídos:**
1. **Price Action puro** (sin RSI, MACD, medias móviles, etc.)
2. **Análisis de estructura de mercado** (swing highs/lows)
3. **Análisis de liquidez** (zonas donde hay stops, barridos de liquidez)
4. **Patrones de alta probabilidad** identificados por IA
5. **Factor de aleatoriedad** para evadir detección de copy-trading en prop firms
6. **Motor de decisión basado en ML/AI** entrenado con datos históricos

### GYR EA (Gerard Garcia)

Del binario se extrajo: `Gerard Garcia`. Es un EA independiente con estrategia propia, también orientado a fondear cuentas.

---

## Deducciones de Lógica de Trading

### Estado de los archivos .ex5

Los archivos `.ex5` están **ofuscados/encriptados**:
- Solo se encuentran strings legibles en metadatos (copyright, URLs)
- No hay nombres de funciones MQL5 visibles
- No se puede extraer el código fuente directamente con strings/hex dump
- **Se requiere decompilador especializado o ingeniería inversa por observación**

### Entrada (Price Action + Estructura + Liquidez)

Basado en la descripción oficial y los parámetros disponibles, la estrategia más probable es:

```
1. ANÁLISIS DE TENDENCIA (sobre velas_periodo velas):
   - Identificar si el precio está haciendo HH/HL (uptrend) o LH/LL (downtrend)
   - Usar el máximo y mínimo del periodo como referencia de estructura

2. DETECCIÓN DE LIQUIDEZ (patrón de entrada):
   - En tendencia alcista:
     → Precio rompe por debajo del mínimo reciente (liquidity sweep / stop hunt)
     → Si el precio recupera y cierra por encima del mínimo → ENTRY LONG
   - En tendencia bajista:
     → Precio rompe por encima del máximo reciente (liquidity sweep / stop hunt)
     → Si el precio recupera y cierra por debajo del máximo → ENTRY SHORT

3. CONFIRMACIÓN (factor IA/patrón):
   - El motor de IA evalúa si el patrón es de "alta probabilidad"
   - Sin acceso al modelo, esta parte debe ser aproximada con reglas deterministas

4. ALEATORIEDAD (anti-detección):
   - Pequeño retraso aleatorio (1-3 velas) antes de ejecutar la entrada
   - Ligera variación en el precio de entrada (± pocos pips)
```

### Salida
- **Stop Loss**: Fijo en pips (definido por `input_sl_pips`)
- **Take Profit**: Derivado del SL × RiskReward (`input_sl_pips × input_RiskReward`)
- Ejemplo US30 M5: SL=4000, RR=1.2 → TP=4800 pips

### Gestión de Lote (Posición)
- El `multiplicador_lotsize` sugiere un sistema de **martingala**
- Valor 1.6 significa que tras una pérdida, el tamaño se multiplica por 1.6
- Tras una ganancia, se resetea al tamaño base
- Esto es típico en bots de fondeo para recuperar drawdowns rápido

### Filtro de Sesiones
- Opera preferentemente en **Londres + Nueva York** (mayor liquidez)
- Asia generalmente desactivada
- Opción de cierre antes del fin de semana

### Gestión de Riesgo Global
- Límites diarios de pérdida/ganancia que detienen el EA
- Contador de pérdidas consecutivas para detener temporalmente
- Esto está alineado con las reglas de prop firms:
  - Daily Loss Limit
  - Max Drawdown
  - Profit Target

---

## Estrategia Propuesta para Replicación

Dado que no podemos extraer el código fuente ni el modelo de IA, implementaremos una **aproximación determinista** basada en los principios descritos:

### Algoritmo Core (Q7)
```
Para cada vela nueva:
  1. Si no hay posición abierta:
     a. Calcular máximo y mínimo de las últimas N velas (velas_periodo)
     b. Determinar tendencia: comparar cierre actual vs cierre de hace N velas
     c. Detectar liquidity sweep:
        - UPTREND + precio rompió mínimo reciente y se recuperó → LONG
        - DOWNTREND + precio rompió máximo reciente y se recuperó → SHORT
     d. Aplicar filtro de sesión (si está activo)
     e. Calcular tamaño de lote según riesgo y balance
     f. Aplicar multiplicador si viene de pérdida
     g. Colocar orden con SL y TP fijos
  
  2. Si hay posición abierta:
     a. Verificar SL/TP
     b. Verificar fin de sesión (cierre forzoso)
     c. Actualizar contadores de P&L diario/semanal/total

  3. Gestión de riesgo:
     a. Si P&L diario >= max_ganancia_diaria → detener hasta siguiente día
     b. Si P&L diario <= -max_perdida_diaria → detener hasta siguiente día
     c. Si pérdidas consecutivas >= max_perdidas_consecutivas → pausa temporal
```

