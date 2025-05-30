const { Client } = require('pg');

class PgPreview {
  description = {
    displayName: 'PostgreSQL Preview',
    name: 'pgPreview',
    group: ['input'],
    version: 1,
    description: 'Query first 10 rows from a PostgreSQL table',
    defaults: {
      name: 'Postgres Preview',
    },
    inputs: ['main'],
    outputs: ['main'],
    credentials: [
      {
        name: 'postgres',
        required: true,
      },
    ],
    properties: [
      {
        displayName: 'Table Name',
        name: 'table',
        type: 'string',
        default: '',
        placeholder: 'your_table_name',
        required: true,
      },
    ],
  };

  async execute() {
    const items = [];
    const table = this.getNodeParameter('table', 0);
    const credentials = this.getCredentials('postgres');

    const client = new Client({
      user: credentials.user,
      password: credentials.password,
      host: credentials.host,
      port: credentials.port,
      database: credentials.database,
      ssl: credentials.ssl || false,
    });

    await client.connect();
    const res = await client.query(`SELECT * FROM ${table} LIMIT 10`);
    await client.end();

    for (const row of res.rows) {
      items.push({ json: row });
    }

    return [items];
  }
}

module.exports = { PgPreview };
