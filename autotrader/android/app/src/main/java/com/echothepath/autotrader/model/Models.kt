package com.echothepath.autotrader.model

data class Scores(val radar:Int=0,val technical:Int=0,val trend:Int=0,val runner:Int=0,val sniper:Int=0)
data class Candle(val time:Long,val open:Double,val high:Double,val low:Double,val close:Double,val volume:Double,val ema20:Double,val ema50:Double)
data class Indicators(
    val ema20:Double=0.0,val ema50:Double=0.0,val ema200:Double=0.0,
    val rsi:Double=0.0,val macd:Double=0.0,val macdSignal:Double=0.0,
    val bollUpper:Double=0.0,val bollLower:Double=0.0,val atr:Double=0.0,
    val volumeRatio:Double=0.0,val support:Double=0.0,val resistance:Double=0.0
)
data class EngineView(
    val symbol:String="BTCUSDT", val price:Double=0.0, val change:Double=0.0,
    val decision:String="WAIT", val reason:String="Motor verisi bekleniyor", val character:String="NEUTRAL",
    val scores:Scores=Scores(), val entryLow:Double=0.0,val entryHigh:Double=0.0,
    val invalidation:Double=0.0,val emergency:Double=0.0,val targets:List<Double> = emptyList(),
    val positionUsdt:Double=0.0,val rewardRisk:Double=0.0,
    val indicators:Indicators=Indicators(), val candles:List<Candle> = emptyList(),
    val timeframes:Map<String,String> = emptyMap(), val connected:Boolean=false
)

data class Mover(val symbol:String,val price:Double,val changePct:Double,val quoteVolume:Double,val score:Double)
