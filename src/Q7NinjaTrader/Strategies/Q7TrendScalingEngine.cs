// Q7TrendScalingEngine.cs
// NinjaTrader 8 Strategy - Signal detector only
// Replica del detector de tendencia del EA_TrendScaling.mq5
// EMA + ADX con confirmacion de 2 barras
// SOLO emite señales CYCLE_START / CYCLE_END, no ejecuta trades

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
    public class Q7TrendScalingEngine : Strategy
    {
        private JavaScriptSerializer json = new JavaScriptSerializer();
        private string signalOutputPath;

        // === TREND TF ===
        private Data.BarsPeriod trendBarsPeriod;
        private Data.BarsPeriodType trendTFType = Data.BarsPeriodType.Minute;
        private int trendTFValue = 5;
        private EMA emaFast, emaSlow;
        private ADX adx;
        private ATR atr;

        private int emaFastPeriod = 20;
        private int emaSlowPeriod = 50;
        private int adxPeriod = 14;
        private double adxThreshold = 20.0;
        private int atrPeriod = 14;

        private bool cycleActive = false;
        private int cycleDirection = 0;
        private int cycleBars = 0;
        private int cooldownBars = 0;
        private int cooldownPeriod = 3;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"Q7 TrendScaling Signal Detector - EMA+ADX trend detection";
                Name = "Q7TrendScalingEngine";
                Calculate = Calculate.OnBarClose;

                TrendTFType = Data.BarsPeriodType.Minute;
                TrendTFValue = 5;
                EmaFastPeriod = 20;
                EmaSlowPeriod = 50;
                AdxPeriod = 14;
                AdxThreshold = 20.0;
                AtrPeriod = 14;
                CooldownPeriod = 3;
            }
            else if (State == State.Configure)
            {
                signalOutputPath = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                    "NinjaTrader 8", "Q7", "signals"
                );
                if (!Directory.Exists(signalOutputPath))
                    Directory.CreateDirectory(signalOutputPath);

                AddDataSeries(TrendTFType, TrendTFValue);
            }
            else if (State == State.DataLoaded)
            {
                emaFast = EMA(BarsArray[1], EmaFastPeriod);
                emaSlow = EMA(BarsArray[1], EmaSlowPeriod);
                adx = ADX(BarsArray[1], AdxPeriod);
                atr = ATR(BarsArray[1], AtrPeriod);

                emaFast.Plots[0].Brush = System.Windows.Media.Brushes.Gold;
                emaSlow.Plots[0].Brush = System.Windows.Media.Brushes.Orange;
                AddChartIndicator(emaFast);
                AddChartIndicator(emaSlow);
            }
        }

        protected override void OnBarUpdate()
        {
            if (BarsInProgress != 0) return;

            // Heartbeat every bar (main series) - only in realtime
            if (State == State.Realtime)
            {
                try
                {
                    string hbFile = Path.Combine(signalOutputPath, "heartbeat.json");
                    File.WriteAllText(hbFile, $"{{\"time\":\"{Time[0]:yyyy-MM-ddTHH:mm:ssZ}\",\"bar\":{CurrentBar},\"close\":{Close[0]:F2},\"engine\":\"TrendScaling\"}}");
                }
                catch { }
            }

            if (CurrentBars[0] < 20 || CurrentBars[1] < Math.Max(EmaSlowPeriod, AdxPeriod) + 10) return;

            if (cooldownBars > 0) { cooldownBars--; return; }

            double emaF0 = emaFast[0];
            double emaS0 = emaSlow[0];
            double emaF1 = emaFast[1];
            double emaS1 = emaSlow[1];
            double adx0 = adx[0];

            // Check cycle end: EMA crossed against direction + ADX weakened
            if (cycleActive)
            {
                cycleBars++;
                bool stillValid = false;

                if (cycleDirection == 1)
                    stillValid = emaF0 > emaS0 && emaF1 > emaS1 && adx0 >= AdxThreshold * 0.7;
                else if (cycleDirection == -1)
                    stillValid = emaF0 < emaS0 && emaF1 < emaS1 && adx0 >= AdxThreshold * 0.7;

                if (!stillValid)
                {
                    int barsLived = cycleBars;
                    SendSignal("CYCLE_END", cycleDirection, atr[0]);
                    cycleActive = false;
                    cycleDirection = 0;
                    cycleBars = 0;
                    cooldownBars = CooldownPeriod;
                    if (State == State.Realtime) Print("Q7TS: CYCLE_END after " + barsLived + " bars");
                    return;
                }
            }

            if (cycleActive) return;

            // Detect new trend: requires ADX > threshold + EMA aligned for 2 bars
            if (adx0 < AdxThreshold) return;

            if (emaF0 > emaS0 && emaF1 > emaS1)
            {
                cycleActive = true;
                cycleDirection = 1;
                cycleBars = 0;
                SendSignal("CYCLE_START", 1, atr[0]);
                if (State == State.Realtime) Print("Q7TS: CYCLE_START LONG | ADX=" + adx0.ToString("F1"));
            }
            else if (emaF0 < emaS0 && emaF1 < emaS1)
            {
                cycleActive = true;
                cycleDirection = -1;
                cycleBars = 0;
                SendSignal("CYCLE_START", -1, atr[0]);
                if (State == State.Realtime) Print("Q7TS: CYCLE_START SHORT | ADX=" + adx0.ToString("F1"));
            }
        }

        private void SendSignal(string type, int direction, double atrValue)
        {
            // Only write signals in real-time, not during historical/transition
            if (State != State.Realtime) return;

            var signal = new Dictionary<string, object>
            {
                ["type"] = type,
                ["timestamp"] = Time[0].ToString("yyyy-MM-ddTHH:mm:ssZ"),
                ["direction"] = direction,
                ["instrument"] = Instrument.FullName,
                ["atr"] = Math.Round(atrValue, 2),
            };

            string fileName = "cyclescale_" + Time[0].ToString("yyyyMMdd_HHmmss") + "_" +
                              Guid.NewGuid().ToString("N").Substring(0, 6) + ".json";
            File.WriteAllText(Path.Combine(signalOutputPath, fileName), json.Serialize(signal));
            Print("Q7TS: Signal -> " + fileName);
        }

        #region Properties

        [NinjaScriptProperty]
        [Display(Name = "Trend TF Type", Order = 0, GroupName = "00. Timeframe")]
        public Data.BarsPeriodType TrendTFType { get { return trendTFType; } set { trendTFType = value; } }

        [NinjaScriptProperty]
        [Range(1, 60)]
        [Display(Name = "Trend TF Value (min)", Order = 1, GroupName = "00. Timeframe")]
        public int TrendTFValue { get { return trendTFValue; } set { trendTFValue = value; } }

        [NinjaScriptProperty][Range(5, 200)]
        [Display(Name = "EMA Fast", Order = 1, GroupName = "01. Trend Detection")]
        public int EmaFastPeriod { get { return emaFastPeriod; } set { emaFastPeriod = value; } }

        [NinjaScriptProperty][Range(10, 300)]
        [Display(Name = "EMA Slow", Order = 2, GroupName = "01. Trend Detection")]
        public int EmaSlowPeriod { get { return emaSlowPeriod; } set { emaSlowPeriod = value; } }

        [NinjaScriptProperty][Range(7, 50)]
        [Display(Name = "ADX Period", Order = 3, GroupName = "01. Trend Detection")]
        public int AdxPeriod { get { return adxPeriod; } set { adxPeriod = value; } }

        [NinjaScriptProperty][Range(10.0, 50.0)]
        [Display(Name = "ADX Threshold", Order = 4, GroupName = "01. Trend Detection")]
        public double AdxThreshold { get { return adxThreshold; } set { adxThreshold = value; } }

        [NinjaScriptProperty][Range(5, 50)]
        [Display(Name = "ATR Period", Order = 5, GroupName = "01. Trend Detection")]
        public int AtrPeriod { get { return atrPeriod; } set { atrPeriod = value; } }

        [NinjaScriptProperty][Range(0, 20)]
        [Display(Name = "Cooldown Bars", Order = 6, GroupName = "01. Trend Detection")]
        public int CooldownPeriod { get { return cooldownPeriod; } set { cooldownPeriod = value; } }

        #endregion
    }
}
