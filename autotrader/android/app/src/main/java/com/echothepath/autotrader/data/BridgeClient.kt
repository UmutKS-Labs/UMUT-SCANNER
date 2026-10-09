package com.echothepath.autotrader.data

import com.echothepath.autotrader.model.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import org.json.JSONArray
import java.net.HttpURLConnection
import java.net.URLEncoder
import java.net.URL

class BridgeClient(private val base:String="http://127.0.0.1:8765") {
    private fun get(path:String):String {
        val c=(URL(base+path).openConnection() as HttpURLConnection).apply { connectTimeout=1800; readTimeout=5000; requestMethod="GET" }
        return try { if(c.responseCode !in 200..299) error("HTTP ${c.responseCode}"); c.inputStream.bufferedReader().use{it.readText()} } finally { c.disconnect() }
    }
    suspend fun state(brain:String,symbol:String):EngineView = withContext(Dispatchers.IO) {
        val json=JSONObject(get("/v1/$brain/state?symbol="+URLEncoder.encode(symbol,"UTF-8")))
        val scores=json.getJSONObject("scores"); val levels=json.getJSONObject("levels")
        val ind=json.optJSONObject("indicators") ?: JSONObject()
        val tfs=json.getJSONObject("timeframes"); val tfMap=mutableMapOf<String,String>()
        tfs.keys().forEach { k -> val x=tfs.getJSONObject(k); tfMap[k]="${if(x.optBoolean("trend_up")) "Yükselen" else "Zayıf"} · RSI ${"%.1f".format(x.optDouble("rsi"))}" }
        val targets=levels.getJSONArray("targets").let { arr -> List(arr.length()){arr.getDouble(it)} }
        val candles=json.optJSONArray("candles")?.let { arr -> List(arr.length()){i->val x=arr.getJSONObject(i);Candle(x.getLong("time"),x.getDouble("open"),x.getDouble("high"),x.getDouble("low"),x.getDouble("close"),x.getDouble("volume"),x.getDouble("ema20"),x.getDouble("ema50"))} } ?: emptyList()
        val indicators=Indicators(
            ema20=ind.optDouble("ema20"),ema50=ind.optDouble("ema50"),ema200=ind.optDouble("ema200"),
            rsi=ind.optDouble("rsi"),macd=ind.optDouble("macd"),macdSignal=ind.optDouble("macd_signal"),
            bollUpper=ind.optDouble("boll_upper"),bollLower=ind.optDouble("boll_lower"),atr=ind.optDouble("atr"),
            volumeRatio=ind.optDouble("volume_ratio"),support=ind.optDouble("support"),resistance=ind.optDouble("resistance")
        )
        EngineView(symbol=json.getString("symbol"),price=levels.getDouble("current"),change=json.optDouble("change_24h",0.0),decision=json.getString("decision"),reason=json.getString("reason"),character=json.getString("character"),scores=Scores(scores.getInt("radar"),scores.getInt("technical"),scores.getInt("trend"),scores.getInt("runner"),scores.getInt("sniper")),entryLow=levels.getDouble("entry_low"),entryHigh=levels.getDouble("entry_high"),invalidation=levels.getDouble("invalidation_stop"),emergency=levels.getDouble("emergency_stop"),targets=targets,positionUsdt=json.getDouble("position_usdt"),rewardRisk=json.getDouble("reward_risk"),indicators=indicators,candles=candles,timeframes=tfMap,connected=true)
    }
    suspend fun movers(brain:String):List<Mover> = withContext(Dispatchers.IO) {
        val arr=JSONArray(get("/v1/$brain/movers")); List(arr.length()){i->val x=arr.getJSONObject(i);Mover(x.getString("symbol"),x.getDouble("price"),x.getDouble("change_pct"),x.getDouble("quote_volume"),x.getDouble("score"))}
    }
    suspend fun system():JSONObject=withContext(Dispatchers.IO){JSONObject(get("/v1/system/state"))}
}
