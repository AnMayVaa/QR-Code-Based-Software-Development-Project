const fs = require('fs');
const mqtt = require('mqtt');

const client = mqtt.connect('mqtt://192.168.106.166:8883');
//const client = mqtt.connect('mqtt://broker.hivemq.com');

const PUBLISHER_TYPE = "json"; // txt, json
const TOPIC = "openhouse/qrscan";

client.on('connect', () => {
  console.log("qrscan publisher connect to broker");

  if (PUBLISHER_TYPE === "txt") {
    watchTxtFile('qr_log.txt', TOPIC);
  } else if (PUBLISHER_TYPE === "json") {
    watchJsonFile('qr_log.json', TOPIC);
  } else {
    console.error("invalid type");
  }
});

let prev_txt_data = 0;

function watchTxtFile(filename, topic) {
  fs.watchFile(filename, { interval: 1000 }, () => {
    const lines = fs.readFileSync(filename, 'utf8').split('\n').filter(Boolean);

    if (lines.length > prev_txt_data) {
      const new_line = lines.slice(prev_txt_data);
      new_line.forEach((line, index) => {
        const [token, location, check, epoch] = line.split(',');
        const message = {
          token,
          location,
          check: Number(check),
          epoch: Number(epoch)
        };
        publishMessage(topic, message, prev_txt_data + index, "TXT");
      });
      prev_txt_data = lines.length;
    }
  });
}

let prev_json_data = 0;

function watchJsonFile(filename, topic) {
  fs.watchFile(filename, { interval: 1000 }, () => {
    const raw_data = fs.readFileSync(filename, 'utf8');
    const data = JSON.parse(raw_data);

    if (data.length > prev_json_data) {
      const new_data = data.slice(prev_json_data);
      new_data.forEach((message, index) => {
        publishMessage(topic, message, prev_json_data + index, "JSON");
      });
      prev_json_data = data.length;
    }
  });
}

function publishMessage(topic, message, index, type) {
  client.publish(topic, JSON.stringify(message));
  console.log(`${type} send message #${index + 1}:`, message);
}
