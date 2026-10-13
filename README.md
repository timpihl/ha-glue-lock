# Glue Lock for Home Assistant

Home Assistant integration for Glue smart locks. It uses the Glue cloud API through a Glue Hub.  
This is an unofficial project. It's not made, supported or endorsed by GlueHome.

## Features

- Lock and unlock from Home Assistant, with a `lock` entity per Glue lock.
- Sensors for battery level, connection status, the last lock event and its time.
- The lock is unavailable when the Glue Hub cannot reach it.
- The lock state always comes from the last lock event that Glue reports. A failed lock operation is never shown as locked.
- The integration never sends a lock or unlock operation by itself, and never sends one again after an error.

## Requirements

- A Glue lock connected to a Glue Hub.
- Home Assistant 2025.2 or later.

## Installation

1. In HACS, open the menu and select **Custom repositories**.
2. Add `https://github.com/timpihl/ha-glue-lock` with the type **Integration**.
3. Install **Glue Lock** and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and select **Glue Lock**.

Without HACS: copy `custom_components/glue_lock` to the `custom_components` folder of your Home Assistant config and restart.

## Setup

The integration needs a Glue API key. The key can unlock your door, so keep it secret. Glue allows 10 API keys per account.

Choose one of two ways during setup:

- **Sign in to Glue and create a key.** Your username and password are sent to Glue once, to create a key named `home-assistant`. Only the key is stored.
- **Enter an API key that I already have.** Create the key yourself, for example with curl:

  ```bash
  curl -i --request POST 'https://user-api.gluehome.com/v1/api-keys' \
    --header 'Content-Type: application/json' \
    -u 'your-glue-username' \
    --data-raw '{"name": "home-assistant", "scopes": ["events.read", "locks.read", "locks.write"]}'
  ```

## Options

| Option | Default | Description |
| --- | --- | --- |
| Time between status reads | 30 s | Minimum 15 s. |
| Fast read after an operation | on | After a lock or unlock from Home Assistant, read the status every 5 seconds for 60 seconds. |

## How the lock state works

- Home Assistant is updated after each status read, so a change made at the door can take up to the poll interval to appear.
- After a lock or unlock from Home Assistant, the entity shows *Locking* or *Unlocking* until Glue reports the new lock event, for at most 60 seconds.
- If Glue reports that the operation failed or timed out, the service call fails with an error and the entity keeps the state from the lock. Check the door.
- If the Glue API does not answer, the last known values are kept for two reads. After the third failed read in a row the entities become unavailable.
- Locks that you add to the Glue account later appear after you reload the integration.

## Development

The API client and the state logic have no Home Assistant imports. Their tests run with only `aiohttp` and `pytest` installed:

```bash
pytest
```

## Credits and license

Apache License 2.0. See `NOTICE`.

The behaviour of this integration follows the Homebridge plugins [GlueHome/homebridge-plugin](https://github.com/GlueHome/homebridge-plugin) by GlueHome and [homebridge-glue-lock-v2](https://github.com/MatsCedergren/homebridge-glue-lock-v2) by Mats Cedergren.
