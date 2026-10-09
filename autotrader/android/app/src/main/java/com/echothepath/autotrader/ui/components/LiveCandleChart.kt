package com.echothepath.autotrader.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.unit.dp
import com.echothepath.autotrader.model.EngineView
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

@Composable
fun LiveCandleChart(view: EngineView) {
    val candles = view.candles.takeLast(56)
    if (candles.isEmpty()) {
        Text("Canlı mum verisi bekleniyor", color = Muted)
        return
    }

    val prices = buildList {
        candles.forEach { add(it.high); add(it.low) }
        listOf(view.entryLow, view.entryHigh, view.invalidation, view.indicators.support, view.indicators.resistance)
            .filter { it > 0.0 }.forEach(::add)
        view.targets.firstOrNull()?.takeIf { it > 0.0 }?.let(::add)
    }
    val rawMin = prices.minOrNull() ?: candles.minOf { it.low }
    val rawMax = prices.maxOrNull() ?: candles.maxOf { it.high }
    val pad = max((rawMax - rawMin) * 0.06, rawMax * 0.001)
    val minPrice = rawMin - pad
    val maxPrice = rawMax + pad
    val range = max(maxPrice - minPrice, maxPrice * 0.0001)
    val maxVolume = max(candles.maxOf { it.volume }, 1.0)

    Column {
        Canvas(
            Modifier
                .fillMaxWidth()
                .height(230.dp)
                .background(Color(0xFF07111D))
        ) {
            val priceHeight = size.height * 0.78f
            val volumeTop = size.height * 0.82f
            val volumeHeight = size.height - volumeTop
            val step = size.width / candles.size.coerceAtLeast(1)
            val bodyWidth = max(2f, step * 0.56f)

            fun y(price: Double): Float = (((maxPrice - price) / range) * priceHeight).toFloat()

            repeat(4) { i ->
                val gy = priceHeight * i / 3f
                drawLine(Muted.copy(alpha = 0.10f), Offset(0f, gy), Offset(size.width, gy), 1f)
            }

            fun level(price: Double, color: Color, alpha: Float = 0.55f) {
                if (price > 0.0 && price in minPrice..maxPrice) {
                    val yy = y(price)
                    drawLine(color.copy(alpha = alpha), Offset(0f, yy), Offset(size.width, yy), 1.25f)
                }
            }

            level(view.indicators.support, Green, 0.28f)
            level(view.indicators.resistance, Red, 0.28f)
            level(view.entryLow, Blue, 0.55f)
            level(view.entryHigh, Blue, 0.55f)
            level(view.invalidation, Red, 0.70f)
            view.targets.firstOrNull()?.let { level(it, Green, 0.55f) }

            candles.forEachIndexed { index, c ->
                val x = step * index + step / 2f
                val up = c.close >= c.open
                val color = if (up) Green else Red
                val yh = y(c.high)
                val yl = y(c.low)
                val yo = y(c.open)
                val yc = y(c.close)
                drawLine(color.copy(alpha = 0.9f), Offset(x, yh), Offset(x, yl), max(1f, bodyWidth * 0.12f))
                val top = min(yo, yc)
                val h = max(2f, abs(yc - yo))
                drawRect(color, Offset(x - bodyWidth / 2f, top), Size(bodyWidth, h))

                val vh = ((c.volume / maxVolume) * volumeHeight).toFloat()
                drawRect(color.copy(alpha = 0.32f), Offset(x - bodyWidth / 2f, size.height - vh), Size(bodyWidth, vh))
            }

            fun emaPath(selector: (Int) -> Double): Path {
                val p = Path()
                candles.forEachIndexed { index, _ ->
                    val x = step * index + step / 2f
                    val yy = y(selector(index))
                    if (index == 0) p.moveTo(x, yy) else p.lineTo(x, yy)
                }
                return p
            }

            drawPath(emaPath { candles[it].ema20 }, Cyan.copy(alpha = 0.92f), style = androidx.compose.ui.graphics.drawscope.Stroke(width = 2f))
            drawPath(emaPath { candles[it].ema50 }, Blue.copy(alpha = 0.86f), style = androidx.compose.ui.graphics.drawscope.Stroke(width = 2f))
        }
        Text(
            "15DK · Mum + Hacim · EMA20/50 · Entry / Stop / Hedef",
            color = Muted,
            modifier = Modifier.padding(top = 6.dp)
        )
    }
}
