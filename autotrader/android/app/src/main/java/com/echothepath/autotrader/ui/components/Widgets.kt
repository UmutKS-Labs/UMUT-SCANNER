package com.echothepath.autotrader.ui.components

import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.*
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

val Bg=Color(0xFF050A12); val Card=Color(0xFF0B1420); val Blue=Color(0xFF118BFF); val Cyan=Color(0xFF1EC8FF); val Green=Color(0xFF20D981); val Red=Color(0xFFFF5C68); val Muted=Color(0xFF8FA6BF)

@Composable fun Panel(title:String,content:@Composable ColumnScope.()->Unit){ Column(Modifier.fillMaxWidth().background(Card,RoundedCornerShape(16.dp)).padding(14.dp)){Text(title,color=Color.White,fontWeight=FontWeight.Bold);Spacer(Modifier.height(10.dp));content()} }
@Composable fun Stat(label:String,value:String,good:Boolean?=null){ Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Text(label,color=Muted);Text(value,color=when(good){true->Green;false->Red;null->Color.White},fontWeight=FontWeight.SemiBold)} }
@Composable fun ScoreChip(label:String,value:Int){ Column(Modifier.border(1.dp,Blue.copy(.45f),RoundedCornerShape(10.dp)).padding(horizontal=10.dp,vertical=7.dp)){Text(label,color=Muted);Text("$value",color=Color.White,fontWeight=FontWeight.Bold)} }
