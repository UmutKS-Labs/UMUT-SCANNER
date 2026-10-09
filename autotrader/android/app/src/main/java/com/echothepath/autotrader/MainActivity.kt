package com.echothepath.autotrader

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.echothepath.autotrader.ui.AppViewModel
import com.echothepath.autotrader.ui.components.*
import com.echothepath.autotrader.ui.screens.BrainScreen

class MainActivity:ComponentActivity(){ override fun onCreate(savedInstanceState:Bundle?){super.onCreate(savedInstanceState);setContent{AutoTraderApp()}} }

@OptIn(ExperimentalMaterial3Api::class)
@Composable fun AutoTraderApp(){
    val vm=remember{AppViewModel()}; LaunchedEffect(Unit){vm.start()}
    var main by remember{mutableIntStateOf(0)}; var sub by remember{mutableIntStateOf(0)}
    MaterialTheme(colorScheme=darkColorScheme(background=Bg,surface=Card,primary=Blue,onBackground=Color.White)){
        Scaffold(containerColor=Bg,topBar={TopAppBar(title={Text("AUTO TRADER",color=Color.White)},actions={AssistChip(onClick={},label={Text("PAPER")})},colors=TopAppBarDefaults.topAppBarColors(containerColor=Bg))},bottomBar={NavigationBar(containerColor=Card){listOf("SPOT","VADELİ","GEÇMİŞ","AUTO").forEachIndexed{i,x->NavigationBarItem(selected=main==i,onClick={main=i;if(i==0)vm.selectBrain("spot");if(i==1)vm.selectBrain("futures")},icon={},label={Text(x)})}}}){pad->
            Column(Modifier.padding(pad)){
                if(main<=1){TabRow(selectedTabIndex=sub,containerColor=Bg,contentColor=Blue){listOf("ANALİZ","DERİN ANALİZ","İŞLEM").forEachIndexed{i,x->Tab(selected=sub==i,onClick={sub=i},text={Text(x)})}};BrainScreen(vm,sub)}
                else if(main==2) HistoryScreen(vm)
                else AutoScreen(vm)
            }
        }
    }
}

@Composable fun HistoryScreen(vm:AppViewModel){ Box(Modifier.fillMaxSize(),contentAlignment=androidx.compose.ui.Alignment.Center){Text("GEÇMİŞ · Ledger verisi bridge üzerinden bağlanacak",color=Color.White)} }
@Composable fun AutoScreen(vm:AppViewModel){ val s=vm.system; Column(Modifier.fillMaxSize().padding(16.dp),verticalArrangement=Arrangement.spacedBy(10.dp)){Panel("SİSTEM DURUMU"){Stat("Motor",s?.optString("engine")?:"BAĞLANTI BEKLENİYOR",s?.optString("engine")=="RUNNING");Stat("Scanner",s?.optString("scanner")?:"—");Stat("SPOT Beyni",s?.optString("spot_brain")?:"—");Stat("VADELİ Beyni",s?.optString("futures_brain")?:"—");Stat("Bridge",s?.optString("bridge")?:"—");Stat("Sürüm",s?.optString("version")?:"—")};Panel("GÜNCELLEME"){Text("Güncelleme manifest katmanı hazır. Yeni Stable doğrulanınca burada tek GÜNCELLE butonu açılacak.",color=Muted)}} }
