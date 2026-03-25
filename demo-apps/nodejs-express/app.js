const express = require('express');
const app = express();

app.get('/', (req, res) => {
  res.json({ message: 'Hello from Express', status: 'running' });
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

const PORT = 3000;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Server running on port ${PORT}`);
});
