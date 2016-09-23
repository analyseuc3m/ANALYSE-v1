<%page args="scatter_array"/>

// Scatter chart for video events dispersion relative to position within video

// Load the Visualization API and the chart package. Currently done on the HTML page.
//google.load('visualization', '1.0', {'packages':['corechart']});

// Set a callback to run when the Google Visualization API is loaded.
google.setOnLoadCallback(
  function() {
    var selectUser = document.getElementById('user').value;
    localStorage.setItem('selectuser',JSON.stringify(selectUser));
    localStorage.setItem('dateJSONevents',JSON.stringify(${scatter_array}));
    //var selectUser = JSON.parse(localStorage['selectuser']);
    //localStorage['selectuser'] = JSON.stringify(${user_for_charts})
    if(selectUser=='#average'){
            drawChart6_2(${scatter_array});
    }else{
            drawChart6(${scatter_array});
    }

  }
);  

// Callback that creates and populates a data table,
// instantiates the chart, passes in the data and
// draws it.
function drawChart6(json_data) {

  var play_event = document.getElementById('playevent').value;
  var pause_event = document.getElementById('pauseevent').value;
  var seek_from_event = document.getElementById('seekfromevent').value;
  var seek_to_event = document.getElementById('seektoevent').value;
  var change_speed_event = document.getElementById('changespeedevent').value;

  var DEFAULT_COLORS = [play_event,pause_event,change_speed_event,seek_from_event,seek_to_event]
  // Instantiate and draw our chart, passing in some options.
  var chart = new google.visualization.ScatterChart(document.getElementById('dispersion_chart'));
  //alert(json_data);
  if (json_data != null && json_data.length > 0) {
    
    // Create the data table.

    var data = new google.visualization.arrayToDataTable(json_data);
    // Set chart options
    var options = {
		    hAxis: {title: 'Position of the video event (seconds)', minValue: 0},
    		vAxis: {textPosition: 'none', minValue: 0, ticks: [1,2,3,4,5]},
		    width : 500,
		    height : 400,
		    colors: DEFAULT_COLORS,
		    legend: {position: 'none'}
		    };
    
    chart.draw(data, options);
    
  } else {   

    var node = document.createTextNode("No data to display.");
    var noData = document.createElement("p");
    noData.appendChild(node);
    document.getElementById('dispersion_chart').innerHTML = "";
    document.getElementById('dispersion_chart').appendChild(noData);
  }  
}

function drawChart6_2(json_data) {

  var play_event = document.getElementById('playevent').value;
  var pause_event = document.getElementById('pauseevent').value;
  var seek_from_event = document.getElementById('seekfromevent').value;
  var seek_to_event = document.getElementById('seektoevent').value;
  var change_speed_event = document.getElementById('changespeedevent').value;

  var DEFAULT_COLORS = [play_event,pause_event,change_speed_event,seek_from_event,seek_to_event]
  // Instantiate and draw our chart, passing in some options.
  var chart = new google.visualization.LineChart(document.getElementById('dispersion_chart'));
  //alert(json_data);
  if (json_data != null && json_data.length > 0) {
    // Create the data table.
    var maxim=0;
    for (var i=0;i<json_data.length;i++){
        if (json_data[i][0]>maxim){
            maxim=json_data[i][0];
        }
    }
    var valores=10;
    var rango=0;

    var vector_rango = [];
    var j=0;
    while(j<=valores){
        vector_rango[j]=rango;
        j=j+1;
        rango+=maxim/valores;
    }
    //var json_eventos=JSON.parse(JSON.stringify(json_data));
    var json_eventos=[]


    json_eventos[0]=JSON.parse(JSON.stringify(json_data[0]));

    for (var j=1;j<vector_rango.length;j++){
        json_eventos[j]=JSON.parse(JSON.stringify(json_data[j]));
        for(var i=1;i<json_data[0].length;i++){
            json_eventos[j][i]=0;
        }
    }

    for (var j=1;j<vector_rango.length;j++){
        json_eventos[j][0]=(vector_rango[j]+vector_rango[j-1])/2;
    }

    var vectorValues = new Array(json_data[0].length-1).fill(0);

    for(var j=1;j<json_data.length;j++){
        for(var i=1;i<vector_rango.length;i++){
            if(json_data[j][0]<vector_rango[i] && json_data[j][0]>vector_rango[i-1]){
                for(var n=1;n<json_eventos[0].length;n++){
                    if(json_data[j][n]!= null){
                        json_eventos[i][n]=json_eventos[i][n]+1;
                        vectorValues[n-1]=vectorValues[n-1]+1;
                    }
                }
            }
        }
    }

    for(var i=1;i<json_eventos.length;i++){
        for(var j=1;j<json_eventos[0].length;j++){
            if(vectorValues[j-1]!=0){
                json_eventos[i][j]=(json_eventos[i][j]/vectorValues[j-1])*100;
            }
        }
    }
    // Porcentaje: // splice(position, numberOfItemsToRemove, item)         array.splice(2, 0, "three");
    var data = new google.visualization.arrayToDataTable(json_eventos);
    var formatter = new google.visualization.NumberFormat(
    	      {suffix: '%', fractionDigits: 1});
    formatter.format(data, 1);
    formatter.format(data, 2);
    formatter.format(data, 3);
    formatter.format(data, 4);
    formatter.format(data, 5);
    // Set chart options
    var options = {
		    hAxis: {title: 'Position of the video event (seconds)', minValue: 0},
    		vAxis: {minValue: 0, viewWindow:{min:0}},
		    colors: DEFAULT_COLORS,
		    curveType: 'function',
		    tooltip: {isHtml: true},
            intervals: { 'style':'line' },
		    legend: {position: 'none'}
		    };
    google.visualization.events.addListener(chart, 'onmouseover', function(hover){
        if(hover){
            $('.google-visualization-tooltip-item:eq(0)').remove() // remove the other info
        }
    })
    chart.draw(data, options);

  } else {

    var node = document.createTextNode("No data to display.");
    var noData = document.createElement("p");
    noData.appendChild(node);
    document.getElementById('dispersion_chart').innerHTML = "";
    document.getElementById('dispersion_chart').appendChild(noData);
  }
}