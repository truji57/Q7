//+------------------------------------------------------------------------+
//|                                              EA_TrendScaling.mq5       |
//|  EA de tendencia con scaling inteligente y gestion de riesgo por capas |
//|                                                                          |
//|  RESUMEN:                                                                |
//|   - Detecta tendencia (EMA + ADX) y abre la primera posicion a favor.    |
//|   - Va sumando posiciones al ciclo cuando el precio se mueve N x ATR     |
//|     desde la ultima entrada, tanto a favor como en contra, siempre que   |
//|     no se rompa la estructura (si se rompe, se considera cambio de       |
//|     tendencia y no se suma).                                             |
//|   - El lotaje de cada nueva entrada se calcula con un multiplicador:     |
//|       * si el movimiento fue A FAVOR  -> lote * MultiplicadorFavor       |
//|       * si el movimiento fue EN CONTRA -> lote * MultiplicadorContra     |
//|   - Gestion de riesgo en 3 capas: ciclo, dia, drawdown de cuenta.        |
//|   - Trailing equity dinamico (por tramos) a nivel de ciclo.              |
//|                                                                          |
//|  IMPORTANTE: Esto es un boceto funcional para pruebas. Antes de usarlo   |
//|  en real, testealo a fondo en Strategy Tester y demo, y revisa que el    |
//|  broker soporte el volumen/step usado.                                   |
//+------------------------------------------------------------------------+
#property copyright "Boceto EA - uso bajo tu propia responsabilidad"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

CTrade trade;

//====================== INPUTS =============================================

input group "=== Identificacion ==="
input int      InpMagic              = 990001;      // Numero magico del EA
input string   InpComentario         = "TrendScale"; // Comentario en ordenes
input bool     InpSignalMode      = false;  // Modo señales (no abre trades, solo escribe señales)
input bool     InpShowPanel       = true;   // Mostrar panel BUY/SELL en el grafico

input group "=== Deteccion de tendencia ==="
input ENUM_TIMEFRAMES InpTrendTF     = PERIOD_CURRENT; // Timeframe de tendencia
input int      InpEMAFast            = 20;           // Periodo EMA rapida
input int      InpEMASlow            = 50;           // Periodo EMA lenta
input int      InpADXPeriod          = 14;           // Periodo ADX
input double   InpADXThreshold       = 20.0;         // ADX minimo para considerar tendencia

input group "=== Entradas / Scaling ==="
input double   InpLoteBase           = 0.10;         // Lote de la primera entrada
input double   InpMultiplicadorFavor = 0.8;           // Multiplicador si suma A FAVOR (ej 0.8 = reduce)
input double   InpMultiplicadorContra= 1.2;           // Multiplicador si suma EN CONTRA (ej 1.2 = aumenta)
input bool     InpAplicarSobreLoteBase = false;        // true=aplica multiplicador sobre lote base, false=sobre el ultimo lote
input int      InpATRPeriod          = 14;            // Periodo ATR para distancia entre niveles
input double   InpFactorATR          = 1.5;           // Distancia entre niveles = ATR * este factor
input double   InpFactorProgresivo   = 0.15;          // Aumento progresivo de distancia por nivel (0 = desactivado)
input int      InpMaxPosicionesCiclo = 6;              // Maximo de posiciones simultaneas por ciclo
input double   InpMaxLoteCiclo       = 5.0;            // Maximo lotaje acumulado por ciclo
input int      InpBarrasEstructura   = 20;             // Barras para calcular swing high/low de estructura

input group "=== Riesgo - Capa Ciclo ==="
input double   InpSLCicloPct         = 2.0;    // Perdida flotante maxima del ciclo (% balance)
input double   InpTPCicloPct         = 3.0;    // Beneficio flotante objetivo del ciclo (% balance)

input group "=== Riesgo - Capa Dia ==="
input double   InpMaxPerdidaDiariaPct = 4.0;   // Perdida maxima diaria (% balance al inicio del dia)
input double   InpMaxGananciaDiariaPct= 6.0;   // Ganancia maxima diaria, opcional (0 = sin limite)

input group "=== Riesgo - Capa Cuenta (Drawdown) ==="
input double   InpMaxDrawdownCuentaPct = 10.0; // Drawdown maximo desde el pico de equity (%)

input group "=== Trailing Equity (a nivel de ciclo) ==="
input double   InpTrailingActivacionPct = 0.8; // % balance de beneficio flotante para armar el trailing
input double   InpTrailingDistBase      = 0.3; // Distancia de trailing minima (%)
input double   InpTrailingDistSlope     = 0.15;// Cuanto crece la distancia por cada % extra de beneficio
input double   InpTrailingDistMax       = 1.2; // Distancia de trailing maxima (%)

input group "=== Horario (opcional) ==="
input bool     InpUsarHorario        = false;  // Activar restriccion horaria
input int      InpHoraInicio         = 8;      // Hora inicio (hora del servidor)
input int      InpHoraFin            = 20;     // Hora fin (hora del servidor)

input group "=== Cierre Diario ==="
input bool     InpCierreDiario       = false;  // Cerrar todo a una hora fija cada dia
input int      InpHoraCierreDiario   = 22;     // Hora de cierre diario
input int      InpMinCierreDiario    = 0;      // Minuto de cierre diario

input group "=== Cierre Viernes ==="
input bool     InpCierreViernes      = false;  // Cerrar todo los viernes
input int      InpHoraCierreViernes  = 20;     // Hora de cierre viernes
input int      InpMinCierreViernes   = 0;      // Minuto de cierre viernes

//====================== ESTADO GLOBAL =======================================

enum ESTADO_CICLO { SIN_SESGO, EN_CICLO };
ESTADO_CICLO g_estado = SIN_SESGO;

double   g_equityPico        = 0.0;
double   g_dailyStartEquity  = 0.0;
datetime g_dailyDay          = 0;
bool     g_eaHalted          = false;
bool     g_dailyBlocked      = false;

double   g_ultimoLote        = 0.0;
double   g_ultimoPrecioEntrada = 0.0;
int      g_direccionCiclo    = 0;      // 1 = long, -1 = short
int      g_nivelesAlcanzados = 0;
bool     g_shownStructureMsg = false;
int      g_reentryCooldown = 0;

// Signal mode
int      g_signalCount = 0;
datetime g_ultimaSenalTime = 0;
string   g_ultimaSenalType  = "";

// Trailing equity de ciclo
bool     g_trailingArmado    = false;
double   g_trailingEquityMax = 0.0;

int      handleEMAFast, handleEMASlow, handleADX, handleATR;

//====================== UTILIDADES ==========================================

double NormalizarLote(double lote)
{
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

   double lotesRedondeados = MathRound(lote / step) * step;
   lotesRedondeados = MathMax(minL, MathMin(maxL, lotesRedondeados));
   return NormalizeDouble(lotesRedondeados, 2);
}

double GetATRValue()
{
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(handleATR, 0, 1, 1, buf) <= 0) return 0.0;
   return buf[0];
}

//--- Cuenta posiciones, lote total y PnL flotante del ciclo actual (por magic)
void GetInfoCiclo(int &numPos, double &loteTotal, double &pnlFlotante)
{
   numPos = 0; loteTotal = 0.0; pnlFlotante = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

      numPos++;
      loteTotal   += PositionGetDouble(POSITION_VOLUME);
      pnlFlotante += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
   }
}

//--- Reconstruye el estado del ciclo al iniciar el EA (por si hubo reinicio)
void ReconstruirEstadoCiclo()
{
   int numPos; double loteTotal; double pnl;
   GetInfoCiclo(numPos, loteTotal, pnl);

   if(numPos == 0)
   {
      g_estado = SIN_SESGO;
      return;
   }

   g_estado = EN_CICLO;
   g_nivelesAlcanzados = numPos - 1;

   // Buscar la posicion mas reciente para recuperar lote/precio/direccion
   datetime masReciente = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

      datetime t = (datetime)PositionGetInteger(POSITION_TIME);
      if(t >= masReciente)
      {
         masReciente = t;
         g_ultimoLote          = PositionGetDouble(POSITION_VOLUME);
         g_ultimoPrecioEntrada = PositionGetDouble(POSITION_PRICE_OPEN);
         g_direccionCiclo      = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      }
   }
}

//====================== TENDENCIA ===========================================

// Devuelve 1 = tendencia alcista, -1 = bajista, 0 = sin tendencia clara
int DetectarTendencia()
{
   double emaFast[], emaSlow[], adx[];
   ArraySetAsSeries(emaFast, true);
   ArraySetAsSeries(emaSlow, true);
   ArraySetAsSeries(adx, true);

   if(CopyBuffer(handleEMAFast, 0, 0, 3, emaFast) <= 0) return 0;
   if(CopyBuffer(handleEMASlow, 0, 0, 3, emaSlow) <= 0) return 0;
   if(CopyBuffer(handleADX,     0, 0, 3, adx)     <= 0) return 0;

   if(adx[0] < InpADXThreshold) return 0; // sin regimen de tendencia claro

   if(emaFast[0] > emaSlow[0] && emaFast[1] > emaSlow[1]) return 1;
   if(emaFast[0] < emaSlow[0] && emaFast[1] < emaSlow[1]) return -1;

   return 0;
}

//--- Swing high/low de las ultimas N barras (para no sumar si se rompe estructura)
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
   else // ventana que cruza medianoche
      return (dt.hour >= InpHoraInicio || dt.hour < InpHoraFin);
}

//====================== CIERRE POR HORA =======================================

bool CheckCierreHorario()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);

   // Cierre diario
   if(InpCierreDiario)
   {
      if(dt.hour == InpHoraCierreDiario && dt.min >= InpMinCierreDiario)
      {
         static bool cerrardoDiarioHoy = false;
         static int lastDayDiario = 0;
         if(dt.day != lastDayDiario) { cerrardoDiarioHoy = false; lastDayDiario = dt.day; }

         if(!cerrardoDiarioHoy && g_estado == EN_CICLO)
         {
            Print("Q7: CIERRE DIARIO programado (", InpHoraCierreDiario, ":", InpMinCierreDiario, "). Cerrando ciclo.");
            CerrarTodoElCiclo();
            cerrardoDiarioHoy = true;
            return true;
         }
      }
   }

   // Cierre viernes
   if(InpCierreViernes && dt.day_of_week == 5)
   {
      if(dt.hour == InpHoraCierreViernes && dt.min >= InpMinCierreViernes)
      {
         static bool cerrardoViernesHoy = false;
         static int lastDayViernes = 0;
         if(dt.day != lastDayViernes) { cerrardoViernesHoy = false; lastDayViernes = dt.day; }

         if(!cerrardoViernesHoy && g_estado == EN_CICLO)
         {
            Print("Q7: CIERRE VIERNES programado (", InpHoraCierreViernes, ":", InpMinCierreViernes, "). Cerrando ciclo.");
            CerrarTodoElCiclo();
            cerrardoViernesHoy = true;
            return true;
         }
      }
   }

   return false;
}

//====================== RIESGO ==============================================

void ActualizarSeguimientoDiario()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   datetime diaActual = StringToTime(StringFormat("%04d.%02d.%02d", dt.year, dt.mon, dt.day));

   if(diaActual != g_dailyDay)
   {
      g_dailyDay         = diaActual;
      g_dailyStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
      g_dailyBlocked     = false;
      Print("Nuevo dia de trading. Equity inicial del dia: ", g_dailyStartEquity);
   }
}

void ActualizarEquityPico()
{
   double equityActual = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equityActual > g_equityPico) g_equityPico = equityActual;
}

//--- Capa 3: drawdown de cuenta. Si salta, cierra todo y detiene el EA.
bool CheckDrawdownKill()
{
   if(g_equityPico <= 0) return false;
   double equityActual = AccountInfoDouble(ACCOUNT_EQUITY);
   double drawdownPct  = (g_equityPico - equityActual) / g_equityPico * 100.0;

   if(drawdownPct >= InpMaxDrawdownCuentaPct)
   {
      Print("!!! DRAWDOWN MAXIMO DE CUENTA ALCANZADO (", DoubleToString(drawdownPct,2),
            "%). Cerrando todo y deteniendo el EA.");
      CerrarTodoElCiclo();
      g_eaHalted = true;
      return true;
   }
   return false;
}

//--- Capa 2: limites diarios. Si saltan, cierra todo y bloquea entradas el resto del dia.
bool CheckLimitesDiarios()
{
   if(g_dailyBlocked) return true;

   double balance    = AccountInfoDouble(ACCOUNT_BALANCE);
   double equityAct  = AccountInfoDouble(ACCOUNT_EQUITY);
   double pnlDiaPct  = (equityAct - g_dailyStartEquity) / g_dailyStartEquity * 100.0;

   if(pnlDiaPct <= -InpMaxPerdidaDiariaPct)
   {
      Print("!!! LIMITE DE PERDIDA DIARIA ALCANZADO (", DoubleToString(pnlDiaPct,2),
            "%). Cerrando todo y bloqueando entradas hasta manana.");
      CerrarTodoElCiclo();
      g_dailyBlocked = true;
      return true;
   }

   if(InpMaxGananciaDiariaPct > 0 && pnlDiaPct >= InpMaxGananciaDiariaPct)
   {
      Print("Objetivo de ganancia diaria alcanzado (", DoubleToString(pnlDiaPct,2),
            "%). Cerrando todo y bloqueando entradas hasta manana.");
      CerrarTodoElCiclo();
      g_dailyBlocked = true;
      return true;
   }
   return false;
}

//--- Capa 1: limites del ciclo actual (SL/TP flotante en % de balance)
bool CheckLimitesCiclo()
{
   int numPos; double loteTotal; double pnlFlotante;
   GetInfoCiclo(numPos, loteTotal, pnlFlotante);
   if(numPos == 0) return false;

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double pnlPct  = pnlFlotante / balance * 100.0;

   if(pnlPct <= -InpSLCicloPct)
   {
      Print("SL de ciclo alcanzado (", DoubleToString(pnlPct,2), "%). Cerrando ciclo.");
      CerrarTodoElCiclo();
      return true;
   }
   if(pnlPct >= InpTPCicloPct)
   {
      Print("TP de ciclo alcanzado (", DoubleToString(pnlPct,2), "%). Cerrando ciclo.");
      CerrarTodoElCiclo();
      return true;
   }
   return false;
}

//--- Trailing equity inteligente a nivel de ciclo
bool CheckTrailingEquity()
{
   int numPos; double loteTotal; double pnlFlotante;
   GetInfoCiclo(numPos, loteTotal, pnlFlotante);
   if(numPos == 0) { g_trailingArmado = false; return false; }

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double pnlPct  = pnlFlotante / balance * 100.0;

   if(!g_trailingArmado)
   {
      if(pnlPct >= InpTrailingActivacionPct)
      {
         g_trailingArmado    = true;
         g_trailingEquityMax = pnlPct;
         Print("Trailing equity ARMADO en +", DoubleToString(pnlPct,2), "%");
      }
      return false;
   }

   // ya armado: actualizar maximo y comprobar retroceso
   if(pnlPct > g_trailingEquityMax) g_trailingEquityMax = pnlPct;

   double extra = MathMax(0.0, g_trailingEquityMax - InpTrailingActivacionPct);
   double distanciaTrailing = MathMin(InpTrailingDistMax,
                                       InpTrailingDistBase + InpTrailingDistSlope * extra);

   double caidaDesdeMax = g_trailingEquityMax - pnlPct;

   if(caidaDesdeMax >= distanciaTrailing || pnlPct <= 0.0)
   {
      Print("Trailing equity disparado. Maximo=", DoubleToString(g_trailingEquityMax,2),
            "% actual=", DoubleToString(pnlPct,2), "%. Cerrando ciclo.");
      CerrarTodoElCiclo();
      return true;
   }
   return false;
}

void CerrarTodoElCiclo()
{
   // En modo señales el cierre lo gestiona SOLO el orquestador por limites
   // (TPC/SLC/PDLL/PDPT/TPG/SLG). No se envia ninguna señal de cierre.
   if(!InpSignalMode)
   {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong ticket = PositionGetTicket(i);
         if(ticket == 0 || !PositionSelectByTicket(ticket)) continue;
         if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
         if((int)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
         trade.PositionClose(ticket);
      }
   }
   g_estado             = SIN_SESGO;
   g_trailingArmado      = false;
   g_trailingEquityMax   = 0.0;
   g_nivelesAlcanzados   = 0;
   g_ultimoLote          = 0.0;
   g_direccionCiclo      = 0;
   g_shownStructureMsg   = false;
   g_reentryCooldown     = 5;  // 5 ticks de espera antes de re-abrir
}

//====================== LOTAJE INTELIGENTE ==================================

// esFavor = true si el nuevo nivel se alcanzo porque el precio siguio a favor de la tendencia
double CalcularSiguienteLote(bool esFavor)
{
   double base = InpAplicarSobreLoteBase ? InpLoteBase : g_ultimoLote;
   double mult = esFavor ? InpMultiplicadorFavor : InpMultiplicadorContra;
   double nuevoLote = base * mult;
   return NormalizarLote(nuevoLote);
}

//====================== ENTRADAS =============================================

//--- Escribe señal a archivo (modo señales)
void PostSignal(string type, int direction, double atr, string extra="")
{
   // Guard anti-spam: solo 1 señal OPEN por tipo cada 2 segundos
   // (evita duplicados por doble click del panel o reinicios del EA)
   if(StringFind(type, "OPEN_") == 0)
   {
      if(type == g_ultimaSenalType && TimeCurrent() - g_ultimaSenalTime < 2)
         return;
      g_ultimaSenalType = type;
      g_ultimaSenalTime = TimeCurrent();
   }

   string json = "{";
   json += "\"type\":\"" + type + "\",";
   json += "\"direction\":" + IntegerToString(direction) + ",";
   json += "\"atr\":" + DoubleToString(atr,2) + ",";
   json += "\"instrument\":\"" + _Symbol + "\"";
   if(extra != "") json += "," + extra;
   json += "}";

   string fileName = "Q7\\signals\\cyclescale_" + IntegerToString(g_signalCount) + ".json";
   int handle = FileOpen(fileName, FILE_WRITE|FILE_TXT);
   if(handle != INVALID_HANDLE)
   {
      FileWriteString(handle, json);
      FileClose(handle);
       g_signalCount++;
       if(type != "HEARTBEAT") Print("Q7: OK ", type);
   }
   else
   {
      Print("Q7: ERR file ", GetLastError());
   }
}

//--- Dibuja flecha en el grafico
void DrawArrow(string prefix, int count, datetime t, double price, color clr, int code)
{
   string name = prefix + TimeToString(t, TIME_DATE|TIME_MINUTES) + "_" + IntegerToString(count);
   ObjectCreate(0, name, OBJ_ARROW, 0, t, price);
   ObjectSetInteger(0, name, OBJPROP_ARROWCODE, code);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
}

void AbrirPrimeraPosicion(int direccion)
{
   double lote = NormalizarLote(InpLoteBase);
   double precio = (direccion == 1) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double atr = GetATRValue();

   if(InpSignalMode)
   {
      string tipo = (direccion == 1) ? "OPEN_LONG" : "OPEN_SHORT";
      PostSignal(tipo, direccion, atr);
      color clr = (direccion == 1) ? clrLime : clrRed;
      int code = (direccion == 1) ? 233 : 234;
      DrawArrow("TS_Start_", g_signalCount, TimeCurrent(), precio, clr, code);
   }
   else
   {
      bool ok;
      trade.SetExpertMagicNumber(InpMagic);
      if(direccion == 1)
         ok = trade.Buy(lote, _Symbol, precio, 0, 0, InpComentario);
      else
         ok = trade.Sell(lote, _Symbol, precio, 0, 0, InpComentario);

      if(ok)
      {
         Print("Ciclo iniciado. Direccion=", direccion, " Lote=", lote, " Precio=", precio);
      }
      else
      {
         Print("Error al abrir primera posicion: ", trade.ResultRetcodeDescription());
         return;
      }
   }

   g_estado                = EN_CICLO;
   g_direccionCiclo        = direccion;
   g_ultimoLote             = lote;
   g_ultimoPrecioEntrada    = precio;
   g_nivelesAlcanzados      = 0;
   g_shownStructureMsg      = false;
}

void EvaluarSumaPosicion()
{
   int numPos; double loteTotal; double pnlFlotante;
   GetInfoCiclo(numPos, loteTotal, pnlFlotante);

   if(numPos >= InpMaxPosicionesCiclo) return;
   if(loteTotal >= InpMaxLoteCiclo) return;

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

   bool esFavor = (movimiento > 0);
   double nuevoLote = CalcularSiguienteLote(esFavor);

   if(InpSignalMode)
   {
      string tipo = (g_direccionCiclo == 1) ? "OPEN_LONG" : "OPEN_SHORT";
      PostSignal(tipo, g_direccionCiclo, atr,
                  "\"favor\":" + (esFavor ? "true" : "false") +
                  ",\"lot\":" + DoubleToString(nuevoLote,2) +
                  ",\"level\":" + IntegerToString(g_nivelesAlcanzados+1));
      color clr = (g_direccionCiclo == 1) ? clrLime : clrRed;
      int code = (g_direccionCiclo == 1) ? 233 : 234;
      DrawArrow("TS_Add_", g_signalCount, TimeCurrent(), precioActual, clr, code);
   }
   else
   {
      double precioEntrada = (g_direccionCiclo == 1) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                                                        : SymbolInfoDouble(_Symbol, SYMBOL_BID);
      bool ok;
      if(g_direccionCiclo == 1)
         ok = trade.Buy(nuevoLote, _Symbol, precioEntrada, 0, 0, InpComentario);
      else
         ok = trade.Sell(nuevoLote, _Symbol, precioEntrada, 0, 0, InpComentario);

      if(ok)
      {
         Print("Suma de posicion #", g_nivelesAlcanzados+1, " (", esFavor ? "A FAVOR" : "EN CONTRA",
               ") Lote=", nuevoLote, " Precio=", precioEntrada);
      }
      else
      {
         Print("Error al sumar posicion: ", trade.ResultRetcodeDescription());
         return;
      }
   }

   g_nivelesAlcanzados++;
   g_ultimoLote          = nuevoLote;
   g_ultimoPrecioEntrada = precioActual;
}

//====================== CICLO DE VIDA DEL EA =================================

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

   g_equityPico       = AccountInfoDouble(ACCOUNT_EQUITY);
   g_dailyStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   g_dailyDay         = 0; // fuerza recalculo en el primer tick

   trade.SetExpertMagicNumber(InpMagic);

    ReconstruirEstadoCiclo();

    // Signal mode path  
    if(InpSignalMode)
        Print("EA_TrendScaling SIGNAL MODE. Signals -> C:\\Users\\danit\\Documents\\NinjaTrader 8\\Q7\\signals\\");
    else
        Print("EA_TrendScaling TRADE MODE.");

    Print("EA_TrendScaling inicializado. Estado=", (g_estado==EN_CICLO ? "EN_CICLO" : "SIN_SESGO"));

    // Panel BUY / SELL
    if(InpShowPanel && InpSignalMode)
    {
       ObjectCreate(0, "Q7_BtnBuy", OBJ_BUTTON, 0, 0, 0);
       ObjectSetInteger(0, "Q7_BtnBuy", OBJPROP_XDISTANCE, 10);
       ObjectSetInteger(0, "Q7_BtnBuy", OBJPROP_YDISTANCE, 50);
       ObjectSetInteger(0, "Q7_BtnBuy", OBJPROP_XSIZE, 80);
       ObjectSetInteger(0, "Q7_BtnBuy", OBJPROP_YSIZE, 30);
       ObjectSetInteger(0, "Q7_BtnBuy", OBJPROP_BGCOLOR, clrGreen);
       ObjectSetInteger(0, "Q7_BtnBuy", OBJPROP_COLOR, clrWhite);
       ObjectSetString(0, "Q7_BtnBuy", OBJPROP_TEXT, "BUY");
       ObjectSetInteger(0, "Q7_BtnBuy", OBJPROP_FONTSIZE, 12);
       ObjectSetInteger(0, "Q7_BtnBuy", OBJPROP_CORNER, CORNER_LEFT_UPPER);

       ObjectCreate(0, "Q7_BtnSell", OBJ_BUTTON, 0, 0, 0);
       ObjectSetInteger(0, "Q7_BtnSell", OBJPROP_XDISTANCE, 100);
       ObjectSetInteger(0, "Q7_BtnSell", OBJPROP_YDISTANCE, 50);
       ObjectSetInteger(0, "Q7_BtnSell", OBJPROP_XSIZE, 80);
       ObjectSetInteger(0, "Q7_BtnSell", OBJPROP_YSIZE, 30);
       ObjectSetInteger(0, "Q7_BtnSell", OBJPROP_BGCOLOR, clrRed);
       ObjectSetInteger(0, "Q7_BtnSell", OBJPROP_COLOR, clrWhite);
       ObjectSetString(0, "Q7_BtnSell", OBJPROP_TEXT, "SELL");
       ObjectSetInteger(0, "Q7_BtnSell", OBJPROP_FONTSIZE, 12);
       ObjectSetInteger(0, "Q7_BtnSell", OBJPROP_CORNER, CORNER_LEFT_UPPER);
    }

    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| ChartEvent handler                                                |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
{
   if(id == CHARTEVENT_OBJECT_CLICK)
   {
      double atr = GetATRValue();
      double precio = 0;

      if(sparam == "Q7_BtnBuy")
      {
         PostSignal("OPEN_LONG", 1, atr);
         precio = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         DrawArrow("TS_Manual_", g_signalCount, TimeCurrent(), precio, clrLime, 233);
      }
      else if(sparam == "Q7_BtnSell")
      {
         PostSignal("OPEN_SHORT", -1, atr);
         precio = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         DrawArrow("TS_Manual_", g_signalCount, TimeCurrent(), precio, clrRed, 234);
      }
   }
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
   ActualizarSeguimientoDiario();
   ActualizarEquityPico();

   // Heartbeat cada 30s (solo en modo señales)
   if(InpSignalMode)
   {
      static datetime lastHb = 0;
      if(TimeCurrent() - lastHb >= 30)
      {
         PostSignal("HEARTBEAT", 0, 0);
         lastHb = TimeCurrent();
      }
   }

   if(g_eaHalted) return;
   if(CheckCierreHorario()) return;
   if(CheckDrawdownKill()) return;
   if(CheckLimitesDiarios()) return;
   if(!DentroDeHorario())
   {
      // fuera de horario: no abrimos nada nuevo, pero seguimos gestionando lo abierto
      if(g_estado == EN_CICLO)
      {
         CheckLimitesCiclo();
         CheckTrailingEquity();
      }
      return;
   }

   if(g_estado == EN_CICLO)
   {
      if(CheckLimitesCiclo()) return;
      if(CheckTrailingEquity()) return;
      EvaluarSumaPosicion();
      return;
   }

   // SIN_SESGO: buscar entrada
   if(g_reentryCooldown > 0)
   {
      g_reentryCooldown--;
      return;
   }
   int tendencia = DetectarTendencia();
   if(tendencia != 0)
      AbrirPrimeraPosicion(tendencia);
}
//+------------------------------------------------------------------------+
