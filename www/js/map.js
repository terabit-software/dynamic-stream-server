var devices = ['nokia','iphone','ipod','ipad','blackberry','x11','android','android 1.5'];
var markersArray = [];
var marker;
var map;

function initialize() {
  var myOptions = {
    center: new google.maps.LatLng(-22.934365, -43.329048),
    zoom: 11,
    mapTypeId: google.maps.MapTypeId.ROADMAP
  };
  map = new google.maps.Map(document.getElementById("map_canvas"), myOptions);
  addCamadas(map);
}

//adiciona as camadas de trânsito e câmeras no mapa
function addCamadas(map){
  addCameras(map);
}

//insere o maker e configura as funções do click
function insereCamera(myLatlng,camera,map,labelCamera,icone){
  marker = new google.maps.Marker({
    position: myLatlng, 
    map: map,
    flat: true,
    icon : icone
  });

  google.maps.event.addListener(marker, 'click', function() {
    window.location=buildVideoUrl(camera);
  });
    
  insereCaption(marker, labelCamera,camera);
  markersArray.push(marker);
}

function buildVideoUrl(cam_id){
    var userAgent = navigator.userAgent.toLowerCase();
    var url = 'viewer.html?id=' + cam_id;

    switch(userAgentDetect(userAgent)){
    case 0: // Nokia
        document.write('Nokia without flash is not supported');
        break;
    case 1: // iphone, ipod ou ipad
    case 2:
    case 3:
    case 6: // Android
        url='/hls/'+cam_id+'/index.m3u8';
        break;
    case 4: // blackberry
        document.write("Blackberry is not supported");
        break;
    case 5: // Linux (flash)
        break;
    case 7: // Old Android (Flash not supported)
        document.write('Android 1.5 does not support flash');
        break;
    default:
        break;
    }

    return (url);
}

function userAgentDetect(userAg){ 
  for(var i = 0; i < devices.length; i++) {
    if (userAg.search(devices[i]) > 0) {
      //document.write('User agent found: '+i);
      return i;
    }
  }
  return -1;
}

// insere a legenda das câmeras
function insereCaption(marker, lblcamera, cam_id) {
    var htmlContent = '<img src="/thumb/' + cam_id + '.jpg" width="320" height="240" alt="Imagem não disponível"></img>'+
                      '<br>Camera ' + cam_id + '<br />' + lblcamera + '<br />';
    var infowindow = new google.maps.InfoWindow({content: htmlContent});
    google.maps.event.addListener(marker, 'mouseover', function() {
        infowindow.open(map,marker);
    });

    google.maps.event.addListener(marker, 'mouseout', function() {
    infowindow.close();
    });
}

