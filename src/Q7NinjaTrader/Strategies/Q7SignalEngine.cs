// Q7SignalEngine.cs
// NinjaTrader 8 Strategy
// Motor de senales: Price Action + Market Structure + Liquidity Sweeps
// Logica de estructura inline (sin dependencia de indicador externo)

#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.IO;
using System.Web.Script.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
#endregion

namespace NinjaTrader.NinjaScript.Strategies.Q7
{
    public enum MarketTrend { UPTREND, DOWNTREND, RANGE }

    public struct SwingPoint
    {
        public int BarIndex;
        public double Price;
        public bool IsHigh;
    }

    public struct MarketStructure
    {
        public MarketTrend Trend;
        public SwingPoint LastSwingHigh;
        public SwingPoint LastSwingLow;
        public SwingPoint PrevSwingHigh;
        public SwingPoint PrevSwingLow;
        public bool IsLiquiditySweepLong;
        public bool IsLiquiditySweepShort;
    }

    public class Q7SignalEngine : Strategy
    {
        private Random random = new Random();
        private int signalCooldownBars = 0;
        private string signalOutputPath;
        private JavaScriptSerializer json = new JavaScriptSerializer();

        private List<SwingPoint> swingHighs = new List<SwingPoint>();
        private List<SwingPoint> swingLows = new List<SwingPoint>();

        private int velasPeriodo = 20;
        private int swingStrength = 2;
        private int sweepRecoveryBars = 3;
        private int slTicks = 75;
        private double riskReward = 1.2;
        private double minSweepSizeATR = 0.3;
        private bool filterNewYork = true;
        private int nyStartHour = 7;
        private int nyEndHour = 14;
        private bool filterLondon = true;
        private int londonStartHour = 3;
        private int londonEndHour = 11;
        private bool filterAsia = false;
        private int asiaStartHour = 18;
        private int asiaEndHour = 3;
        private int gmtOffset = 3;
        private bool closeFriday = false;
        private bool enableRandomness = true;
        private int randomDelayMin = 0;
        private int randomDelayMax = 2;
        private int entryCooldown = 5;

        // HotKeys: Ctrl+L = LONG, Ctrl+S = SHORT
        private bool enableHotKeys = true;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"Q7 Signal Engine - Price Action + Liquidity Sweep";
                Name = "Q7SignalEngine";
                Calculate = Calculate.OnBarClose;

                VelasPeriodo = 10;
                SwingStrength = 2;
                SweepRecoveryBars = 3;
                SlTicks = 75;
                RiskReward = 1.2;
                MinSweepSizeATR = 0.0;
                FilterNewYork = false;
                NyStartHour = 7;
                NyEndHour = 14;
                FilterLondon = false;
                LondonStartHour = 3;
                LondonEndHour = 11;
                FilterAsia = false;
                AsiaStartHour = 18;
                AsiaEndHour = 3;
                GmtOffset = 3;
                CloseFriday = false;
                EnableRandomness = true;
                RandomDelayMin = 0;
                RandomDelayMax = 2;
                EntryCooldown = 2;
            }
            else if (State == State.Configure)
            {
                signalOutputPath = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                    "NinjaTrader 8", "Q7", "signals"
                );
                if (!Directory.Exists(signalOutputPath))
                    Directory.CreateDirectory(signalOutputPath);
            }
        }
        private int debugBarCount = 0;

        protected override void OnBarUpdate()
        {
            if (CurrentBar < VelasPeriodo + SwingStrength) return;

            // Heartbeat every bar
            try
            {
                string hbFile = Path.Combine(signalOutputPath, "heartbeat.json");
                File.WriteAllText(hbFile, $"{{\"time\":\"{Time[0]:yyyy-MM-ddTHH:mm:ssZ}\",\"bar\":{CurrentBar},\"close\":{Close[0]:F2}}}");
            }
            catch { }

            // Debug: print every 500 bars
            debugBarCount++;
            if (debugBarCount % 500 == 0)
                Print($"Q7 DEBUG: Bar={CurrentBar} Time={Time[0]} Close={Close[0]:F2}");

            if (Position.MarketPosition != MarketPosition.Flat) return;

            if (signalCooldownBars > 0)
            {
                signalCooldownBars--;
                return;
            }

            if (!IsTradingSession()) return;

            MarketStructure structure = AnalyzeStructure();

            if (debugBarCount % 500 == 0)
                Print($"Q7 DEBUG: Trend={structure.Trend} SweepL={structure.IsLiquiditySweepLong} SweepS={structure.IsLiquiditySweepShort}");

            if (structure.Trend == MarketTrend.RANGE) return;

            bool signalLong = false;
            bool signalShort = false;

            if (structure.IsLiquiditySweepLong)
            {
                double atrValue = ATR(14)[0];
                double sweepSize = Math.Abs(structure.LastSwingLow.Price - Low[1]);
                if (sweepSize >= atrValue * MinSweepSizeATR)
                    signalLong = true;
            }
            else if (structure.IsLiquiditySweepShort)
            {
                double atrValue = ATR(14)[0];
                double sweepSize = Math.Abs(High[1] - structure.LastSwingHigh.Price);
                if (sweepSize >= atrValue * MinSweepSizeATR)
                    signalShort = true;
            }

            if (!signalLong && !signalShort)
            {
                if (debugBarCount % 500 == 0)
                    Print($"Q7 DEBUG: ATR filter failed. ATR={ATR(14)[0]:F2} MinSweep={ATR(14)[0] * MinSweepSizeATR:F2}");
                return;
            }

            int delay = enableRandomness ? random.Next(RandomDelayMin, RandomDelayMax + 1) : 0;

            string action = signalLong ? "ENTER_LONG" : "ENTER_SHORT";
            double entryPrice = signalLong ? High[0] + (enableRandomness ? random.Next(-5, 6) : 0) : Low[0] - (enableRandomness ? random.Next(-5, 6) : 0);
            int tpValue = (int)(SlTicks * RiskReward);

            Print($"Q7 SIGNAL: {action} at {Time[0]} Price={entryPrice:F2} SL={SlTicks} TP={tpValue}");

            var signal = new Dictionary<string, object>
            {
                ["type"] = "SIGNAL",
                ["timestamp"] = Time[0].ToString("yyyy-MM-ddTHH:mm:ssZ"),
                ["action"] = action,
                ["order"] = new Dictionary<string, object>
                {
                    ["instrument"] = Instrument.FullName,
                    ["entry_price"] = entryPrice,
                    ["sl_ticks"] = SlTicks,
                    ["tp_ticks"] = tpValue,
                    ["rr_ratio"] = RiskReward
                },
                ["structure"] = new Dictionary<string, object>
                {
                    ["trend"] = structure.Trend.ToString(),
                    ["last_swing_high"] = structure.LastSwingHigh.Price,
                    ["last_swing_low"] = structure.LastSwingLow.Price
                }
            };

            string timestamp = Time[0].ToString("yyyyMMdd_HHmmss");
            string fileName = "signal_" + timestamp + "_" + Guid.NewGuid().ToString("N") + ".json";
            string filePath = Path.Combine(signalOutputPath, fileName);

            File.WriteAllText(filePath, json.Serialize(signal));
            Print("Q7: Signal published -> " + filePath);

            signalCooldownBars = EntryCooldown + delay;
        }

        // ============== STRUCTURE ANALYSIS (inline, no external indicator) ==============

        private MarketStructure AnalyzeStructure()
        {
            MarketStructure structure = new MarketStructure();

            int startBar = CurrentBar - VelasPeriodo;
            if (startBar < 0) startBar = 0;

            // Find period extremes for structure
            double periodHigh = High[CurrentBar - 1];
            double periodLow = Low[CurrentBar - 1];
            int highBar = CurrentBar - 1;
            int lowBar = CurrentBar - 1;

            for (int i = startBar; i < CurrentBar; i++)
            {
                if (High[i] > periodHigh) { periodHigh = High[i]; highBar = i; }
                if (Low[i] < periodLow) { periodLow = Low[i]; lowBar = i; }
            }

            // Build 2 swing points from extremes
            swingHighs.Clear();
            swingLows.Clear();
            swingHighs.Add(new SwingPoint { BarIndex = startBar, Price = High[startBar], IsHigh = true });
            swingHighs.Add(new SwingPoint { BarIndex = highBar, Price = periodHigh, IsHigh = true });
            swingLows.Add(new SwingPoint { BarIndex = startBar, Price = Low[startBar], IsHigh = false });
            swingLows.Add(new SwingPoint { BarIndex = lowBar, Price = periodLow, IsHigh = false });

            structure.LastSwingHigh = swingHighs[1];
            structure.PrevSwingHigh = swingHighs[0];
            structure.LastSwingLow = swingLows[1];
            structure.PrevSwingLow = swingLows[0];

            // Simple trend: compare close now vs close N bars ago
            double closeNow = Close[0];
            double closeOld = Close[VelasPeriodo];
            double change = (closeNow - closeOld) / closeOld;

            if (change > 0.0005)  // +0.05%
                structure.Trend = MarketTrend.UPTREND;
            else if (change < -0.0005)  // -0.05%
                structure.Trend = MarketTrend.DOWNTREND;
            else
                structure.Trend = MarketTrend.UPTREND;  // default to uptrend to allow more signals

            structure.IsLiquiditySweepLong = DetectLiquiditySweepLong(structure);
            structure.IsLiquiditySweepShort = DetectLiquiditySweepShort(structure);

            return structure;
        }

        private bool IsSwingHigh(int bar)
        {
            double high = High[bar];
            for (int i = 1; i <= SwingStrength; i++)
            {
                if (bar - i >= 0 && High[bar - i] >= high) return false;
                if (bar + i < Count && High[bar + i] >= high) return false;
            }
            return true;
        }

        private bool IsSwingLow(int bar)
        {
            double low = Low[bar];
            for (int i = 1; i <= SwingStrength; i++)
            {
                if (bar - i >= 0 && Low[bar - i] <= low) return false;
                if (bar + i < Count && Low[bar + i] <= low) return false;
            }
            return true;
        }

        private bool DetectLiquiditySweepLong(MarketStructure structure)
        {
            // Check if recent low was swept and price recovered
            for (int lookback = 1; lookback <= 5; lookback++)
            {
                if (CurrentBar < lookback + 2) continue;

                double recentLow = Low[lookback];

                // Check bars 0 to (lookback-1) broke below recentLow
                for (int i = 0; i < lookback; i++)
                {
                    if (Low[i] < recentLow && Close[i] > recentLow)
                        return true;
                }
            }
            return false;
        }

        private bool DetectLiquiditySweepShort(MarketStructure structure)
        {
            for (int lookback = 1; lookback <= 5; lookback++)
            {
                if (CurrentBar < lookback + 2) continue;

                double recentHigh = High[lookback];

                for (int i = 0; i < lookback; i++)
                {
                    if (High[i] > recentHigh && Close[i] < recentHigh)
                        return true;
                }
            }
            return false;
        }

        // ============== SESSION FILTER ==============

        private bool IsTradingSession()
        {
            // Si ningun filtro esta activo, operar 24h
            if (!FilterLondon && !FilterNewYork && !FilterAsia)
                return true;

            DateTime serverTime = Time[0];
            int gmtHour = (serverTime.Hour + GmtOffset + 24) % 24;

            bool inLondon = FilterLondon && gmtHour >= LondonStartHour && gmtHour < LondonEndHour;
            bool inNY = FilterNewYork && gmtHour >= NyStartHour && gmtHour < NyEndHour;
            bool inAsia = FilterAsia && (
                (AsiaStartHour < AsiaEndHour && gmtHour >= AsiaStartHour && gmtHour < AsiaEndHour)
                || (AsiaStartHour > AsiaEndHour && (gmtHour >= AsiaStartHour || gmtHour < AsiaEndHour))
            );

            if (CloseFriday && serverTime.DayOfWeek == DayOfWeek.Friday && gmtHour >= 20)
                return false;

            return inLondon || inNY || inAsia;
        }

        // ============== PROPERTIES ==============

        #region Properties

        [NinjaScriptProperty]
        [Range(5, 200)]
        [Display(Name = "Velas Periodo", Order = 1, GroupName = "01. Estructura")]
        public int VelasPeriodo { get { return velasPeriodo; } set { velasPeriodo = value; } }

        [NinjaScriptProperty]
        [Range(1, 5)]
        [Display(Name = "Swing Strength", Order = 2, GroupName = "01. Estructura")]
        public int SwingStrength { get { return swingStrength; } set { swingStrength = value; } }

        [NinjaScriptProperty]
        [Range(1, 10)]
        [Display(Name = "Sweep Recovery Bars", Order = 3, GroupName = "01. Estructura")]
        public int SweepRecoveryBars { get { return sweepRecoveryBars; } set { sweepRecoveryBars = value; } }

        [NinjaScriptProperty]
        [Range(5, 5000)]
        [Display(Name = "SL Ticks", Order = 1, GroupName = "02. Entrada")]
        public int SlTicks { get { return slTicks; } set { slTicks = value; } }

        [NinjaScriptProperty]
        [Range(0.5, 5.0)]
        [Display(Name = "Risk/Reward", Order = 2, GroupName = "02. Entrada")]
        public double RiskReward { get { return riskReward; } set { riskReward = value; } }

        [NinjaScriptProperty]
        [Range(0.0, 1.0)]
        [Display(Name = "Min Sweep Size (ATR)", Order = 3, GroupName = "02. Entrada")]
        public double MinSweepSizeATR { get { return minSweepSizeATR; } set { minSweepSizeATR = value; } }

        [NinjaScriptProperty]
        [Display(Name = "Filter New York", Order = 1, GroupName = "03. Sesiones")]
        public bool FilterNewYork { get { return filterNewYork; } set { filterNewYork = value; } }

        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "NY Start Hour (GMT)", Order = 2, GroupName = "03. Sesiones")]
        public int NyStartHour { get { return nyStartHour; } set { nyStartHour = value; } }

        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "NY End Hour (GMT)", Order = 3, GroupName = "03. Sesiones")]
        public int NyEndHour { get { return nyEndHour; } set { nyEndHour = value; } }

        [NinjaScriptProperty]
        [Display(Name = "Filter London", Order = 4, GroupName = "03. Sesiones")]
        public bool FilterLondon { get { return filterLondon; } set { filterLondon = value; } }

        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "London Start Hour (GMT)", Order = 5, GroupName = "03. Sesiones")]
        public int LondonStartHour { get { return londonStartHour; } set { londonStartHour = value; } }

        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "London End Hour (GMT)", Order = 6, GroupName = "03. Sesiones")]
        public int LondonEndHour { get { return londonEndHour; } set { londonEndHour = value; } }

        [NinjaScriptProperty]
        [Display(Name = "Filter Asia", Order = 7, GroupName = "03. Sesiones")]
        public bool FilterAsia { get { return filterAsia; } set { filterAsia = value; } }

        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "Asia Start Hour (GMT)", Order = 8, GroupName = "03. Sesiones")]
        public int AsiaStartHour { get { return asiaStartHour; } set { asiaStartHour = value; } }

        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "Asia End Hour (GMT)", Order = 9, GroupName = "03. Sesiones")]
        public int AsiaEndHour { get { return asiaEndHour; } set { asiaEndHour = value; } }

        [NinjaScriptProperty]
        [Range(-12, 12)]
        [Display(Name = "GMT Offset", Order = 10, GroupName = "03. Sesiones")]
        public int GmtOffset { get { return gmtOffset; } set { gmtOffset = value; } }

        [NinjaScriptProperty]
        [Display(Name = "Close Friday EOD", Order = 11, GroupName = "03. Sesiones")]
        public bool CloseFriday { get { return closeFriday; } set { closeFriday = value; } }

        [NinjaScriptProperty]
        [Display(Name = "Enable Randomness", Order = 1, GroupName = "04. Anti-deteccion")]
        public bool EnableRandomness { get { return enableRandomness; } set { enableRandomness = value; } }

        [NinjaScriptProperty]
        [Range(0, 10)]
        [Display(Name = "Random Delay Min Bars", Order = 2, GroupName = "04. Anti-deteccion")]
        public int RandomDelayMin { get { return randomDelayMin; } set { randomDelayMin = value; } }

        [NinjaScriptProperty]
        [Range(0, 10)]
        [Display(Name = "Random Delay Max Bars", Order = 3, GroupName = "04. Anti-deteccion")]
        public int RandomDelayMax { get { return randomDelayMax; } set { randomDelayMax = value; } }

        [NinjaScriptProperty]
        [Range(1, 50)]
        [Display(Name = "Entry Cooldown Bars", Order = 4, GroupName = "04. Anti-deteccion")]
        public int EntryCooldown { get { return entryCooldown; } set { entryCooldown = value; } }

        #endregion
    }
}
