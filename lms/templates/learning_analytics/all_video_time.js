<%page args="video_distrib_json"/>

// Load the Visualization API and the chart package. Currently done on the HTML page.
//google.load("visualization", "1", {packages:["corechart"]});

// Set a callback to run when the Google Visualization API is loaded.
google.setOnLoadCallback(
  function() {
    localStorage['dateJSON2'] = JSON.stringify(${video_distrib_json});
    drawChart2(${video_distrib_json});
}
);

// Callback that creates and populates a data table,
// instantiates the chart, passes in the data and
// draws it.
function drawChart2(json_data) {

  // Instantiate and draw our chart, passing in some options.
  var chart = new google.visualization.BarChart(document.getElementById('all_video_time'));
  
  if (json_data != null && json_data.length > 0) {

    var vectorValues = [];
    var vectorNames =[];
    var sumvalues =0;

    json_data[0][2]={type: 'string', role: 'tooltip'};
    var video_names_sorted=${video_names_sorted};

    var json = [];
    var cont=1;
    json [0] = json_data[0];
    for (var j=0; j<video_names_sorted.length; j++) {
	    for (var i=1;i<json_data.length; i++) {
	        var n = (json_data[i][0]).localeCompare(video_names_sorted[j]);
            if (n==0){
                //Assign the value of the video selected
                json [cont] = json_data[i];
                cont= 1 + cont;
            }
	    }
	}


    for (var i=1;i<json.length;i++){
        vectorValues[i-1]=json[i][1];
        vectorNames[i-1]=json[i][0];
        sumvalues=sumvalues+json[i][1];
    }

    for (var j=1;j<json.length;j++){
        json[j][1]=(json[j][1]/sumvalues)*100;
        json[j][2]= vectorValues[j-1] + ' min' + '\n' + (json[j][1].toFixed(2)) +' %';

    }

    var json_limit= [];
    var cont=1;
    json_limit [0] = json[0];
    var cent=1;
    for (var i=1;i<json.length; i++) {
        if(cent<9){
            json_limit [cent] = json[i];
            cent=1+cent;
        }
    }
    // Create the data table.
    var data = new google.visualization.arrayToDataTable(json_limit);
    
    var formatter = new google.visualization.NumberFormat(
  	      {suffix: ' min', pattern:'#,###%', fractionDigits: '1'});
    formatter.format(data, 1);
    var COLOR = document.getElementById('vidActivity').value;
    // Set chart options
    var options = {
      legend: {position: 'none'},
      tooltip: {isHtml: true},
      colors: [COLOR],
    };
    
    chart.draw(data, options);
    
  } else {   

    var node = document.createTextNode("No data to display.");
    var noData = document.createElement("p");
    noData.appendChild(node);
    document.getElementById('all_video_time').innerHTML = "";
    document.getElementById('all_video_time').appendChild(noData);
    
  }

}

function drawChart2_2(json_data) {

  // Instantiate and draw our chart, passing in some options.
  var chart = new google.visualization.BarChart(document.getElementById('all_video_time'));

  if (json_data != null && json_data.length > 0) {


    // Create the data table.
    var data = new google.visualization.arrayToDataTable(json_data);

    var formatter = new google.visualization.NumberFormat(
  	      {suffix: ' min', pattern:'#,###%', fractionDigits: '1'});
    formatter.format(data, 1);
    var COLOR = document.getElementById('vidActivity').value;
    // Set chart options
    var options = {
      legend: {position: 'none'},
      tooltip: {isHtml: true},
      colors: [COLOR],
    };

    chart.draw(data, options);

  } else {

    var node = document.createTextNode("No data to display.");
    var noData = document.createElement("p");
    noData.appendChild(node);
    document.getElementById('all_video_time').innerHTML = "";
    document.getElementById('all_video_time').appendChild(noData);

  }

}