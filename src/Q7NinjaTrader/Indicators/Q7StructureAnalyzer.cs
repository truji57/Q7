// Q7StructureAnalyzer.cs
// NinjaTrader 8 Indicator
// Detecta estructura de mercado: swing highs/lows y tendencia por price action
//
// Para instalar: Copiar a Documents\NinjaTrader 8\bin\Custom\Indicators\
// Compilar desde NinjaScript Editor

#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.SuperDom;
using NinjaTrader.Gui.Tools;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.Indicators.Q7
{
    public enum MarketTrend
    {
        UPTREND,
        DOWNTREND,
        RANGE
    }

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

    public class Q7StructureAnalyzer : Indicator
    {
        private int lookbackPeriod = 20;
        private int swingStrength = 2;
        private int sweepRecoveryBars = 3;

        private List<SwingPoint> swingHighs = new List<SwingPoint>();
        private List<SwingPoint> swingLows = new List<SwingPoint>();

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"Q7 Market Structure Analyzer - Price Action swing points and liquidity sweep detection";
                Name = "Q7StructureAnalyzer";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                DisplayInDataBox = true;
                DrawOnPricePanel = true;
                DrawHorizontalGridLines = true;
                DrawVerticalGridLines = true;
                PaintPriceMarkers = true;
                ScaleJustification = NinjaTrader.Gui.Chart.ScaleJustification.Right;

                LookbackPeriod = 20;
                SwingStrength = 2;
                SweepRecoveryBars = 3;
            }
            else if (State == State.Configure)
            {
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < LookbackPeriod + SwingStrength) return;

            Analyze();
        }

        private void Analyze()
        {
            swingHighs.Clear();
            swingLows.Clear();

            int startBar = CurrentBar - LookbackPeriod;
            if (startBar < 0) startBar = 0;

            for (int i = startBar + SwingStrength; i <= CurrentBar - SwingStrength; i++)
            {
                if (IsSwingHigh(i, SwingStrength))
                {
                    swingHighs.Add(new SwingPoint
                    {
                        BarIndex = i,
                        Price = High[i],
                        IsHigh = true
                    });
                }

                if (IsSwingLow(i, SwingStrength))
                {
                    swingLows.Add(new SwingPoint
                    {
                        BarIndex = i,
                        Price = Low[i],
                        IsHigh = false
                    });
                }
            }
        }

        private bool IsSwingHigh(int bar, int strength)
        {
            double high = High[bar];
            for (int i = 1; i <= strength; i++)
            {
                if (bar - i >= 0 && High[bar - i] >= high) return false;
                if (bar + i < Count && High[bar + i] >= high) return false;
            }
            return true;
        }

        private bool IsSwingLow(int bar, int strength)
        {
            double low = Low[bar];
            for (int i = 1; i <= strength; i++)
            {
                if (bar - i >= 0 && Low[bar - i] <= low) return false;
                if (bar + i < Count && Low[bar + i] <= low) return false;
            }
            return true;
        }

        public MarketStructure GetStructure()
        {
            MarketStructure structure = new MarketStructure();

            if (swingHighs.Count >= 2 && swingLows.Count >= 2)
            {
                structure.LastSwingHigh = swingHighs[swingHighs.Count - 1];
                structure.PrevSwingHigh = swingHighs[swingHighs.Count - 2];
                structure.LastSwingLow = swingLows[swingLows.Count - 1];
                structure.PrevSwingLow = swingLows[swingLows.Count - 2];

                bool higherHigh = structure.LastSwingHigh.Price > structure.PrevSwingHigh.Price;
                bool higherLow = structure.LastSwingLow.Price > structure.PrevSwingLow.Price;
                bool lowerHigh = structure.LastSwingHigh.Price < structure.PrevSwingHigh.Price;
                bool lowerLow = structure.LastSwingLow.Price < structure.PrevSwingLow.Price;

                if (higherHigh && higherLow)
                    structure.Trend = MarketTrend.UPTREND;
                else if (lowerHigh && lowerLow)
                    structure.Trend = MarketTrend.DOWNTREND;
                else
                    structure.Trend = MarketTrend.RANGE;

                structure.IsLiquiditySweepLong = DetectLiquiditySweepLong(structure);
                structure.IsLiquiditySweepShort = DetectLiquiditySweepShort(structure);
            }

            return structure;
        }

        private bool DetectLiquiditySweepLong(MarketStructure structure)
        {
            if (structure.Trend != MarketTrend.UPTREND) return false;

            double sweepLevel = structure.LastSwingLow.Price;

            for (int i = 1; i <= SweepRecoveryBars && i < CurrentBar; i++)
            {
                bool brokeBelow = Low[i] < sweepLevel;
                bool recovered = Close[i] > sweepLevel;
                bool prevBelow = Close[i + 1] < sweepLevel;

                if (brokeBelow && recovered && prevBelow)
                    return true;
            }

            return false;
        }

        private bool DetectLiquiditySweepShort(MarketStructure structure)
        {
            if (structure.Trend != MarketTrend.DOWNTREND) return false;

            double sweepLevel = structure.LastSwingHigh.Price;

            for (int i = 1; i <= SweepRecoveryBars && i < CurrentBar; i++)
            {
                bool brokeAbove = High[i] > sweepLevel;
                bool recovered = Close[i] < sweepLevel;
                bool prevAbove = Close[i + 1] > sweepLevel;

                if (brokeAbove && recovered && prevAbove)
                    return true;
            }

            return false;
        }

        #region Properties

        [NinjaScriptProperty]
        [Range(5, 200)]
        [Display(Name = "Lookback Period", Description = "Number of bars to analyze for structure", Order = 1, GroupName = "Parameters")]
        public int LookbackPeriod
        {
            get { return lookbackPeriod; }
            set { lookbackPeriod = value; }
        }

        [NinjaScriptProperty]
        [Range(1, 5)]
        [Display(Name = "Swing Strength", Description = "Bars on each side to confirm a swing point", Order = 2, GroupName = "Parameters")]
        public int SwingStrength
        {
            get { return swingStrength; }
            set { swingStrength = value; }
        }

        [NinjaScriptProperty]
        [Range(1, 10)]
        [Display(Name = "Sweep Recovery Bars", Description = "Max bars for liquidity sweep recovery confirmation", Order = 3, GroupName = "Parameters")]
        public int SweepRecoveryBars
        {
            get { return sweepRecoveryBars; }
            set { sweepRecoveryBars = value; }
        }

        #endregion
    }
}
