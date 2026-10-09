package com.echothepath.autotrader.ui

import androidx.compose.runtime.*
import com.echothepath.autotrader.data.BridgeClient
import com.echothepath.autotrader.model.*
import kotlinx.coroutines.*
import org.json.JSONObject

class AppViewModel {
    private val scope=CoroutineScope(SupervisorJob()+Dispatchers.Main.immediate)
    private val client=BridgeClient()
    var brain by mutableStateOf("spot"); private set
    var symbol by mutableStateOf("BTCUSDT"); private set
    var view by mutableStateOf(EngineView()); private set
    var movers by mutableStateOf(emptyList<Mover>()); private set
    var system by mutableStateOf<JSONObject?>(null); private set
    var error by mutableStateOf<String?>(null); private set
    private var poll:Job?=null

    fun selectBrain(v:String){ if(brain!=v){brain=v; refresh()} }
    fun selectSymbol(v:String){ symbol=v.uppercase(); refresh() }
    fun start(){ if(poll!=null)return; poll=scope.launch { while(isActive){ refresh(); delay(7000) } } }
    fun refresh(){ scope.launch { try { val s=client.state(brain,symbol); val m=client.movers(brain); val sys=client.system(); view=s; movers=m; system=sys; error=null } catch(e:Exception){ error=e.message; view=view.copy(connected=false) } } }
}
