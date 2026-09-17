const fs = require("fs");

function required(name) {
    const value = process.env[name];
    if (!value) {
        throw new Error(name + " must be provisioned");
    }
    return value;
}

module.exports = {
    uiPort: 1880,
    uiHost: "0.0.0.0",
    flowFile: "flows.json",
    credentialSecret: fs.readFileSync(required("NODE_RED_CREDENTIAL_SECRET_FILE"), "utf8").trim(),
    adminAuth: {
        type: "credentials",
        sessionExpiryTime: 1800,
        users: [{
            username: "admin",
            password: required("NODE_RED_ADMIN_PASSWORD_HASH"),
            permissions: "*"
        }]
    },
    httpAdminRoot: "/editor",
    httpNodeRoot: "/flows",
    disableEditor: false,
    functionExternalModules: false,
    externalModules: {
        autoInstall: false,
        autoInstallRetry: 0,
        palette: { allowInstall: false, allowUpdate: false, allowUpload: false },
        modules: { allowInstall: false }
    },
    editorTheme: {
        projects: { enabled: false },
        palette: { editable: false },
        header: { title: "OmniGate Edge Flows" }
    },
    logging: {
        console: { level: "info", metrics: false, audit: true }
    }
};
