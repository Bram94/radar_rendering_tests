export async function generateVertices(url) {
  //get file from server
  var t = new Date().getTime();
  const response = await fetch(url);
  const gzip_blob = await response.blob();
  const array = new Uint8Array(await gzip_blob.arrayBuffer());
  const text = pako.ungzip(array, {to: "string"});
  const json = JSON.parse(text);
  console.log(new Date().getTime()-t, "fetch and parse json");

  const firstGate = json.first_gate;
  const gateRes = json.gate_spacing;
  const totalVertices = json.total_bins*6;
  var azs = json.azimuths;
  var min = azs[0];
  var max = azs[azs.length-1];
    
  var pos = new Float32Array(2*totalVertices);
  var colors = new Float32Array(totalVertices);
  var indices = new Int32Array([]);

  var n = 0;
  var leftAz, rightAz, bottomR, topR, values, az, colorVal, ranges;
  for (var key in json.radials) {
    key = +key;
    ranges = (new Float32Array(json.radials[key])).map(x => firstGate+x*gateRes);
    az = azs[key];

    //case when first az
    if (key == 0) {
      //case when crossing 0
      leftAz = (min + 360 + max)/2;
      rightAz = (az+azs[key+1])/2;
    } else if (key == azs.length-1) {
      //case when crossing 0 the other way
      leftAz = (az + azs[key-1])/2;
      rightAz = (min+360+max)/2; 
    } else {
      //case when nothing to worry about
      leftAz = (az + azs[key-1])/2;
      rightAz = (az + azs[key+1])/2;
    }
    
    //loop through radar range gates
    for (var i=0; i<ranges.length; i++) {
      bottomR = ranges[i] - gateRes/2;
      topR = ranges[i] + gateRes/2;
      
      pos[2*n] = bottomR;
      pos[2*n+1] = leftAz;
      pos[2*n+2] = topR;
      pos[2*n+3] = leftAz;
      pos[2*n+4] = bottomR;
      pos[2*n+5] = rightAz;
      
      pos[2*n+6] = bottomR;
      pos[2*n+7] = rightAz;
      pos[2*n+8] = topR;
      pos[2*n+9] = leftAz;
      pos[2*n+10] = topR;
      pos[2*n+11] = rightAz;
      
      colorVal = json.values[key][i];
      for (var j=0; j<6; j++) {
        colors[n+j] = colorVal;
      }
      
      n += 6;
    }
  }
  
  console.log(new Date().getTime()-t, "loop");
  return { pos, indices, colors };
}
