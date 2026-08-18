//+------------------------------------------------------------------------+
//|                                          Q7_SignalGenerator.mq5         |
//|  Generador de señales Q7 (SOLO MODO SEÑALES)                            |
//|                                                                          |
//|  Extraido de EA_TrendScaling quitando todo lo que el modo señal          |
//|  no utiliza: gestion de riesgo, calculo de lotaje y ejecucion de trades. |
//|                                                                          |
//|  FUNCIONAMIENTO:                                                         |
//|   - Detecta tendencia (EMA rapida/lenta + ADX) y emite OPEN_LONG/        |
//|     OPEN_SHORT como PRIMERA entrada del ciclo.                           |
//|   - Mientras el precio se mueve N x ATR desde la ultima entrada, emite   |
//|     nuevas OPEN_LONG/OPEN_SHORT (suma de posiciones) siempre que no se   |
//|     rompa la estructura (swing high/low).                                |
//|   - Si la tendencia se pierde durante 5 ticks, el ciclo termina y el     |
//|     generador queda listo para una nueva señal.                          |
//|   - Heartbeat cada 30s.                                                  |
//|   - NO abre trades: solo escribe JSON en Q7\signals\cyclescale_*.json    |
//|     que el orquestador Python lee para gestionar cuentas en NT8.         |
//|                                                                          |
//|  La gestion real del riesgo (TPC/SLC/PDLL/PDPT/TPG/SLG), el cierre y el  |
//|  lotaje los decide el orquestador. Este EA solo genera señales.          |
//+------------------------------------------------------------------------+
#property copyright "Q7 - Modo señales"
#property version   "1.00"
#property strict

//====================== INPUTS =============================================

input group "=== Identificacion ==="
input bool     InpShowPanel       = true;   // Mostrar panel BUY/SELL en el grafico

input group "=== Deteccion de tendencia ==="
input ENUM_TIMEFRAMES InpTrendTF     = PERIOD_CURRENT; // Timeframe de tendencia
input int      InpEMAFast            = 20;           // Periodo EMA rapida
input int      InpEMASlow            = 50;           // Periodo EMA lenta
input int      InpADXPeriod          = 14;           // Periodo ADX
input double   InpADXThreshold       = 20.0;         // ADX minimo para considerar tendencia

input group "=== Entradas / Scaling ==="
input int      InpATRPeriod          = 14;            // Periodo ATR para distancia entre niveles
input double   InpFactorATR          = 1.5;           // Distancia entre niveles = ATR * este factor
input double   InpFactorProgresivo   = 0.15;          // Aumento progresivo de distancia por nivel (0 = desactivado)
input int      InpMaxPosicionesCiclo = 6;              // Maximo de señales de entrada por ciclo
input int      InpBarrasEstructura   = 20;             // Barras para calcular swing high/low de estructura

//====================== ESTADO GLOBAL =======================================

enum ESTADO_CICLO { SIN_SESGO, EN_CICLO };
ESTADO_CICLO g_estado = SIN_SESGO;

datetime g_initTime          = 0;   // momento de OnInit, para cooldown de arranque
double   g_ultimoPrecioEntrada = 0.0;
int      g_direccionCiclo    = 0;      // 1 = long, -1 = short
int      g_nivelesAlcanzados = 0;
bool     g_shownStructureMsg = false;
int      g_reentryCooldown   = 0;

// Estado de señales
int      g_signalCount = 0;
datetime g_ultimaSenalTime = 0;
string   g_ultimaSenalType  = "";
int      g_ticksSinTendencia = 0;

// Persistencia de estado (sobrevive a recargas del EA: recompilar / reiniciar MT5)
string   g_stateFile = "Q7\\signals\\q7_signalgenerator_state.json";

int      handleEMAFast, handleEMASlow, handleADX, handleATR;

//====================== TENDENCIA ===========================================

// Devuelve 1 = tendencia alcista, -1 = bajista, 0 = sin tendencia clara
int DetectarTendencia()
{
   // Warm-up guard: los indicadores no emiten valores validos hasta que
   // han calculado al menos su propio periodo
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

//====================== SEÑALES =============================================

double GetATRValue()
{
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(handleATR, 0, 1, 1, buf) <= 0) return 0.0;
   return buf[0];
}

//--- Escribe señal a archivo
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

//--- Persiste el estado del generador para sobrevivir a recargas (recompilar /
//    reiniciar MT5). NO habla con el orquestador: solo recuerda la ultima señal
//    enviada y el estado del ciclo para no re-emitir al recargar.
void GuardarEstado()
{
   int h = FileOpen(g_stateFile, FILE_WRITE|FILE_TXT);
   if(h == INVALID_HANDLE) return;
   string content = StringFormat(
      "{\"estado\":%d,\"dir\":%d,\"niveles\":%d,\"senalType\":\"%s\",\"senalTime\":%d,\"count\":%d,\"precio\":%.5f}",
      (int)g_estado, g_direccionCiclo, g_nivelesAlcanzados,
      g_ultimaSenalType, (int)g_ultimaSenalTime, g_signalCount,
      g_ultimoPrecioEntrada);
   FileWriteString(h, content);
   FileClose(h);
}

//--- Restaura el estado persistido
void CargarEstado()
{
   if(!FileIsExist(g_stateFile)) return;
   int h = FileOpen(g_stateFile, FILE_READ|FILE_TXT);
   if(h == INVALID_HANDLE) return;
   string content = FileReadString(h);
   FileClose(h);

   // parseo minimo del JSON (sin librerias)
   g_estado             = (ESTADO_CICLO)LeerJsonInt(content, "estado");
   g_direccionCiclo     = LeerJsonInt(content, "dir");
   g_nivelesAlcanzados  = LeerJsonInt(content, "niveles");
   g_ultimaSenalType    = LeerJsonStr(content, "senalType");
   g_ultimaSenalTime    = (datetime)LeerJsonInt(content, "senalTime");
   g_signalCount        = LeerJsonInt(content, "count");
   g_ultimoPrecioEntrada = LeerJsonDbl(content, "precio");

   if(g_estado != SIN_SESGO && g_estado != EN_CICLO) g_estado = SIN_SESGO;
   Print("Q7: estado restaurado -> ", (g_estado==EN_CICLO ? "EN_CICLO" : "SIN_SESGO"),
         " dir=", g_direccionCiclo, " nivel=", g_nivelesAlcanzados);
}

int LeerJsonInt(string s, string key)
{
   string v = LeerJsonStr(s, key);
   if(v == "") return 0;
   return (int)StringToInteger(v);
}

double LeerJsonDbl(string s, string key)
{
   string v = LeerJsonStr(s, key);
   if(v == "") return 0.0;
   return StringToDouble(v);
}

string LeerJsonStr(string s, string key)
{
   string needle = "\"" + key + "\":";
   int pos = StringFind(s, needle);
   if(pos < 0) return "";
   int start = pos + StringLen(needle);
   if(StringGetCharacter(s, start) == '"')
   {
      start++;
      int end = StringFind(s, "\"", start);
      if(end < 0) return "";
      return StringSubstr(s, start, end - start);
   }
   int end = StringFind(s, ",", start);
   int end2 = StringFind(s, "}", start);
   if(end2 >= 0 && (end < 0 || end2 < end)) end = end2;
   if(end < 0) return "";
   return StringSubstr(s, start, end - start);
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

//====================== ENTRADAS =============================================

//--- Primera entrada del ciclo (solo señal)
void EmitirEntrada(int direccion)
{
   double atr = GetATRValue();
   double precio = (direccion == 1) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);

   string tipo = (direccion == 1) ? "OPEN_LONG" : "OPEN_SHORT";
   PostSignal(tipo, direccion, atr);
   color clr = (direccion == 1) ? clrLime : clrRed;
   int code = (direccion == 1) ? 233 : 234;
   DrawArrow("TS_Start_", g_signalCount, TimeCurrent(), precio, clr, code);

   g_estado              = EN_CICLO;
   g_direccionCiclo      = direccion;
   g_ultimoPrecioEntrada = precio;
   g_nivelesAlcanzados   = 0;
   g_shownStructureMsg   = false;
   g_ticksSinTendencia   = 0;
   GuardarEstado();
}

//--- Suma de posicion (solo señal): el precio se movio N x ATR desde la ultima entrada
void EvaluarSumaPosicion()
{
   if(g_nivelesAlcanzados >= InpMaxPosicionesCiclo) return;

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
   string tipo = (g_direccionCiclo == 1) ? "OPEN_LONG" : "OPEN_SHORT";
   PostSignal(tipo, g_direccionCiclo, atr,
              "\"favor\":" + (esFavor ? "true" : "false") +
              ",\"level\":" + IntegerToString(g_nivelesAlcanzados + 1));
   color clr = (g_direccionCiclo == 1) ? clrLime : clrRed;
   int code = (g_direccionCiclo == 1) ? 233 : 234;
   DrawArrow("TS_Add_", g_signalCount, TimeCurrent(), precioActual, clr, code);

   g_nivelesAlcanzados++;
   g_ultimoPrecioEntrada = precioActual;
   GuardarEstado();
}

//--- Reset del ciclo (tendencia perdida): el generador queda listo para nueva señal
void ResetEstadoCiclo()
{
   g_estado              = SIN_SESGO;
   g_direccionCiclo      = 0;
   g_nivelesAlcanzados   = 0;
   g_ultimoPrecioEntrada = 0.0;
   g_shownStructureMsg   = false;
   g_reentryCooldown     = 5;  // 5 ticks de espera antes de re-abrir
   g_ticksSinTendencia   = 0;
   GuardarEstado();
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

   g_initTime = TimeCurrent();

   // Restauramos la ultima señal enviada (evita re-emitir al recargar)
   CargarEstado();

   Print("Q7_SignalGenerator: señales -> Q7\\signals\\cyclescale_*.json");
   Print("Q7_SignalGenerator inicializado. Estado=", (g_estado==EN_CICLO ? "EN_CICLO" : "SIN_SESGO"));

   // Panel BUY / SELL (señal manual)
   if(InpShowPanel)
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
   // Heartbeat cada 30s
   static datetime lastHb = 0;
   if(TimeCurrent() - lastHb >= 30)
   {
      PostSignal("HEARTBEAT", 0, 0);
      lastHb = TimeCurrent();
   }

   if(g_estado == EN_CICLO)
   {
      // Si la tendencia se pierde, el ciclo termina para el generador
      // y puede buscar una nueva entrada.
      int t = DetectarTendencia();
      if(t == 0)
      {
         g_ticksSinTendencia++;
         if(g_ticksSinTendencia >= 5)
         {
            Print("Q7: tendencia perdida -> SIN_SESGO (listo para nueva señal)");
            ResetEstadoCiclo();
            return;
         }
      }
      else
      {
         g_ticksSinTendencia = 0;
      }

      EvaluarSumaPosicion();
      return;
   }

   // SIN_SESGO: buscar entrada
   if(g_reentryCooldown > 0)
   {
      g_reentryCooldown--;
      return;
   }
   // Cooldown de arranque: no buscar entrada en los primeros segundos tras OnInit
   // (evita orden espuria al iniciar MT5 o al anadir el EA por primera vez)
   if(TimeCurrent() - g_initTime < 5)
      return;
   int tendencia = DetectarTendencia();
   if(tendencia != 0)
      EmitirEntrada(tendencia);
}
//+------------------------------------------------------------------------+
