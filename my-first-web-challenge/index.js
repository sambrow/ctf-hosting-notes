let express = require('express');
let app = express();

app.get('/', function(req, res) {
    res.sendFile(__dirname + '/index.html')
});

let port = 8000;
let server = app.listen(port);
console.log('Local server running on port: ' + port);
