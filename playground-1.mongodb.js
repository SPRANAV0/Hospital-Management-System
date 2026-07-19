// 1. Tell MongoDB which database to open (replace with your DB name)
use('my_first_database');

// 2. Insert a document into a collection called 'users'
db.getCollection('users').insertOne({
  name: "Pranav",
  role: "Developer",
  joined: new Date()
});

// 3. View everything inside your 'users' collection
db.getCollection('users').find({});