const functions = require('firebase-functions');
const admin = require('firebase-admin');
admin.initializeApp();

exports.deleteUnverifiedAccounts = functions.pubsub.schedule('every 1 hours').onRun(async (context) => {
  const db = admin.firestore();
  const cutoffTime = new Date(Date.now() - 24 * 60 * 60 * 1000); // 24 hours ago

  try {
    const snapshot = await db.collection('temp_users')
      .where('created_at', '<', cutoffTime)
      .get();

    const batch = db.batch();
    const authPromises = [];

    snapshot.forEach(doc => {
      const userData = doc.data();
      batch.delete(doc.ref);
      authPromises.push(admin.auth().deleteUser(doc.id));
      console.log(`Deleting unverified user: ${userData.email}`);
    });

    await Promise.all([batch.commit(), ...authPromises]);
    console.log(`Deleted ${snapshot.size} unverified accounts`);
    return null;
  } catch (error) {
    console.error('Error deleting unverified accounts:', error);
    return null;
  }
});