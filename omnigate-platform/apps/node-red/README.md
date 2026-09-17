# OmniGate Node-RED application profile

This bundle is for the **Enhanced** runtime on RK3568, T536, and similarly
sized products. It is intentionally excluded from RK3506 and other Lite
images. The editor is bound to loopback and must be published through the
OmniGate authenticated HTTPS proxy.

Before deployment, provision `NODE_RED_ADMIN_PASSWORD_HASH` with:

```sh
node-red admin hash-pw
```

Node-RED exchanges normalized data with the edge runtime over MQTT instead of
opening CAN, serial, GPIO, or raw Ethernet devices inside the container.
The broker hostname is supplied through `OMNIGATE_MQTT_HOST`; the Enhanced
compose profile sets it to the private service name `omnigate-mqtt`.

On the first start, `init-data.sh` copies the packaged `settings.js` and
`flows.json` into the writable `node-red-data` volume.  It never overwrites an
existing file, so editor deployments, flows, and encrypted credentials remain
available after a container restart or image upgrade.
