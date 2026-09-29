//+------------------------------------------------------------------------+
//|                                    Q7_SignalGenerator_Backtest.mq5     |
//|  Backtest del generador de señales Q7 (1 señal = 1 orden, con limite)  |
//|                                                                        |
//|  Derivado de Q7_SignalGenerator.mq5. Replica la generacion de señales  |
//|  del original: entrada por tendencia (EMA+ADX) + "adds" cuando el      |
//|  precio se mueve N x ATR desde la ultima entrada.                      |
//|                                                                        |
//|  Cada señal abre UNA orden real con SL/TP fijos en puntos.             |
//|  NO mira si ya hay posiciones abiertas (igual que el orquestador):     |
//|  solo esta limitado por InpMaxPosiciones (equivalente al MXP).         |
//|                                                                        |
//|  Cambios respecto al original:                                         |
//|   - Cada señal abre una orden con SL/TP fijos en puntos.               |
//|   - Parametro InpMaxPosiciones para limitar ordenes simultaneas.       |
//|   - Horario de operativa opcional.                                     |
//|   - Sin escritura de JSON, sin panel BUY/SELL, sin persistencia.       |
//|                                                                        |
//|  La orden sale SIEMPRE por TP o SL (lo gestiona el tester).            |
//+------------------------------------------------------------------------+
#property copyright "Q7 - Backtest"
#property version   "1.20"
#property strict

#include <Trade/Trade.mqh>

CTrade trade;

//====================== INPUTS =============================================

input group "=== Operativa ==="
input double   InpTPPuntos      = 22.5;   // Take Profit en puntos de precio
input double   InpSLPuntos      = 47.0;   // Stop Loss en puntos de precio
input double   InpLote          = 0.01;   // Volumen por orden
input int      InpMaxPosiciones = 6;      // Max de ordenes abiertas simultaneas (MXP)
input int      InpMagic         = 990002; // Numero magico
input string   InpComentario    = "Q7BT"; // Comentario en ordenes

input group "=== Horario (hora del servidor) ==="
input bool     InpUsarHorario = true;   // Activar restriccion horaria
input int      InpHoraInicio  = 7;      // Hora inicio (inclusive)
input int      InpHoraFin     = 14;     // Hora fin (exclusive)

input group "=== Deteccion de tendencia (copia de SignalGenerator) ==="
input ENUM_TIMEFRAMES InpTrendTF = PERIOD_CURRENT; // Timeframe de tendencia
input int      InpEMAFast      = 20;    // Periodo EMA rapida
input int      InpEMASlow      = 50;    // Periodo EMA lenta
input int      InpADXPeriod    = 14;    // Periodo ADX
input double   InpADXThreshold = 20.0;  // ADX minimo para considerar tendencia

input group "=== Entradas / Scaling (distancia entre ordenes) ==="
input int      InpATRPeriod        = 14;   // Periodo ATR para distancia entre niveles
input double   InpFactorATR        = 1.5;  // Distancia entre niveles = ATR * factor
input double   InpFactorProgresivo = 0.15; // Aumento progresivo por nivel (0 = desactivado)
input int      InpBarrasEstructura = 20;   // Barras para swing high/low de estructura

//====================== ESTADO ==============================================

enum ESTADO_CICLO { SIN_SESGO, EN_CICLO };
ESTADO_CICLO g_estado = SIN_SESGO;

int      g_direccionCiclo      = 0;
double   g_ultimoPrecioEntrada = 0.0;
int      g_nivelesAlcanzados   = 0;
bool     g_shownStructureMsg   = false;
int      g_ticksSinTendencia   = 0;
int      g_reentryCooldown     = 0;
int      g_signalCount         = 0;

int handleEMAFast, handleEMASlow, handleADX, handleATR;

//====================== TENDENCIA ===========================================

int DetectarTendencia()
{
   int ready = MathMin(BarsCalculated(handleEMAFast),
                       MathMin(BarsCalculated(handleEMASlow),
                               BarsCalculated(handleADX)));
   if(ready < MathMax(InpEMASlow, InpADXPeriod))
      return 0;

   double emaFast[], emaSlow[], adx[];
   ArraySetAsSeries(emaFast, true);
   ArraySetAsSeries(emaSlow, true);
   ArraySetAsSeries(adx, true);

   if(CopyBuffer(handleEMAFast, 0, 0, 3, emaFast) <= 0) return 0;
   if(CopyBuffer(handleEMASlow, 0, 0, 3, emaSlow) <= 0) return 0;
   if(CopyBuffer(handleADX,     0, 0, 3, adx)     <= 0) return 0;

   if(adx[0] < InpADXThreshold) return 0;

   if(emaFast[0] > emaSlow[0] && emaFast[1] > emaSlow[1]) return 1;
   if(emaFast[0] < emaSlow[0] && emaFast[1] < emaSlow[1]) return -1;

   return 0;
}

//====================== ATR / ESTRUCTURA ====================================

double GetATRValue()
{
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(handleATR, 0, 1, 1, buf) <= 0) return 0.0;
   return buf[0];
}

void GetSwing(int barras, double &swingHigh, double &swingLow)
{
   swingHigh = iHigh(_Symbol, InpTrendTF, iHighest(_Symbol, InpTrendTF, MODE_HIGH, barras, 1));
   swingLow  = iLow(_Symbol, InpTrendTF,  iLowest(_Symbol, InpTrendTF, MODE_LOW,  barras, 1));
}

//====================== HORARIO =============================================

bool DentroDeHorario()
{
   if(!InpUsarHorario) return true;
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   if(InpHoraInicio <= InpHoraFin)
      return (dt.hour >= InpHoraInicio && dt.hour < InpHoraFin);
   return (dt.hour >= InpHoraInicio || dt.hour < InpHoraFin);
}

//====================== POSICIONES ==========================================

int PosicionesAbiertas()
{
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      n++;
   }
   return n;
}

//====================== FLECHAS =============================================

void DrawArrow(string prefix, int count, datetime t, double price, color clr, int code)
{
   string name = prefix + TimeToString(t, TIME_DATE|TIME_MINUTES) + "_" + IntegerToString(count);
   ObjectCreate(0, name, OBJ_ARROW, 0, t, price);
   ObjectSetInteger(0, name, OBJPROP_ARROWCODE, code);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
}

//====================== ENTRADA =============================================

double AbrirOperacion(int direccion, string prefix)
{
   double ask    = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid    = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   int    digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

   double sl = 0, tp = 0, precio = 0;
   if(direccion == 1)
   {
      precio = ask;
      sl = NormalizeDouble(ask - InpSLPuntos, digits);
      tp = NormalizeDouble(ask + InpTPPuntos, digits);
      if(trade.Buy(InpLote, _Symbol, ask, sl, tp, InpComentario))
         DrawArrow(prefix, g_signalCount++, TimeCurrent(), ask, clrLime, 233);
   }
   else
   {
      precio = bid;
      sl = NormalizeDouble(bid + InpSLPuntos, digits);
      tp = NormalizeDouble(bid - InpTPPuntos, digits);
      if(trade.Sell(InpLote, _Symbol, bid, sl, tp, InpComentario))
         DrawArrow(prefix, g_signalCount++, TimeCurrent(), bid, clrRed, 234);
   }

   g_ultimoPrecioEntrada = precio;
   return precio;
}

//====================== ADD (SUMA DE POSICION) ==============================

void EvaluarSumaPosicion()
{
   if(PosicionesAbiertas() >= InpMaxPosiciones) return;

   double atr = GetATRValue();
   if(atr <= 0) return;

   double distanciaNivel = atr * InpFactorATR * (1.0 + InpFactorProgresivo * g_nivelesAlcanzados);

   double precioActual = (g_direccionCiclo == 1) ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                                                   : SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   double movimiento = (g_direccionCiclo == 1) ? (precioActual - g_ultimoPrecioEntrada)
                                                : (g_ultimoPrecioEntrada - precioActual);

   // Estructura
   double swingHigh, swingLow;
   GetSwing(InpBarrasEstructura, swingHigh, swingLow);
   bool estructuraRota = (g_direccionCiclo == 1) ? (precioActual < swingLow)
                                                   : (precioActual > swingHigh);
   if(estructuraRota)
   {
      if(!g_shownStructureMsg)
      {
         Print("Estructura rota en contra del ciclo. No se suma.");
         g_shownStructureMsg = true;
      }
      return;
   }

   if(MathAbs(movimiento) < distanciaNivel) return;

   AbrirOperacion(g_direccionCiclo, "Q7BT_Add_");
   g_nivelesAlcanzados++;
}

//====================== RESET DEL CICLO =====================================

void ResetEstadoCiclo()
{
   g_estado              = SIN_SESGO;
   g_direccionCiclo      = 0;
   g_ultimoPrecioEntrada = 0.0;
   g_nivelesAlcanzados   = 0;
   g_shownStructureMsg   = false;
   g_ticksSinTendencia   = 0;
   g_reentryCooldown     = 5;
}

//====================== CICLO DE VIDA =======================================

int OnInit()
{
   handleEMAFast = iMA(_Symbol, InpTrendTF, InpEMAFast, 0, MODE_EMA, PRICE_CLOSE);
   handleEMASlow = iMA(_Symbol, InpTrendTF, InpEMASlow, 0, MODE_EMA, PRICE_CLOSE);
   handleADX     = iADX(_Symbol, InpTrendTF, InpADXPeriod);
   handleATR     = iATR(_Symbol, InpTrendTF, InpATRPeriod);

   if(handleEMAFast == INVALID_HANDLE || handleEMASlow == INVALID_HANDLE ||
      handleADX == INVALID_HANDLE || handleATR == INVALID_HANDLE)
   {
      Print("Error creando indicadores.");
      return INIT_FAILED;
   }

   trade.SetExpertMagicNumber(InpMagic);
   Print("Q7_SignalGenerator_Backtest inicializado. TP=", InpTPPuntos,
         " SL=", InpSLPuntos, " MaxPos=", InpMaxPosiciones,
         " horario=", InpHoraInicio, "-", InpHoraFin);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   IndicatorRelease(handleEMAFast);
   IndicatorRelease(handleEMASlow);
   IndicatorRelease(handleADX);
   IndicatorRelease(handleATR);
}

void OnTick()
{
   // EN_CICLO: igual que el original, el ciclo termina cuando la tendencia
   // se pierde 5 ticks. Mientras, va sumando posiciones (adds) dentro del
   // horario y hasta InpMaxPosiciones.
   if(g_estado == EN_CICLO)
   {
      int t = DetectarTendencia();
      if(t == 0)
      {
         g_ticksSinTendencia++;
         if(g_ticksSinTendencia >= 5)
         {
            ResetEstadoCiclo();
            return;
         }
      }
      else
      {
         g_ticksSinTendencia = 0;
      }

      if(DentroDeHorario())
         EvaluarSumaPosicion();
      return;
   }

   // SIN_SESGO: buscar nueva entrada
   if(g_reentryCooldown > 0)
   {
      g_reentryCooldown--;
      return;
   }
   if(!DentroDeHorario()) return;
   if(PosicionesAbiertas() >= InpMaxPosiciones) return;

   int tendencia = DetectarTendencia();
   if(tendencia != 0)
   {
      AbrirOperacion(tendencia, "Q7BT_Start_");
      g_estado              = EN_CICLO;
      g_direccionCiclo      = tendencia;
      g_nivelesAlcanzados   = 0;
      g_shownStructureMsg   = false;
      g_ticksSinTendencia   = 0;
   }
}
//+------------------------------------------------------------------------+
