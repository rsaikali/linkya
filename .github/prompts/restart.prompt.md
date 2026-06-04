---
mode: 'agent'
description: 'Restart cleanly the application.'
---

To restart the application cleanly, follow these steps:

1. Stop the application gracefully to allow ongoing requests to complete.
2. Clean up any temporary files or caches.
3. Rebuild any necessary components if applicable.
4. Start the application again.

Make sure to monitor the application logs for any errors during the restart process.
Do not delete any volumes or persistent data.
Do not restart any services outside of the application itself.