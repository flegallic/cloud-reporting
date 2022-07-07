## Vault sidecar injector on k8s
Un conteneur Vault jouant le role d'agent doit être créé sur le cluster, afin, de restituer les secrets sur un volume de mémoire partagée, à l'aide de modèles d'agent Vault. En rendant les secrets sur un volume partagé, les conteneurs du pod peuvent consommer les secrets Vault. Cela permet de rendre transparent la partie Authentification/JWT-Tokens.

### Documentation
https://www.vaultproject.io/docs/platform/k8s/injector \
https://kubernetes.io/docs/reference/access-authn-authz/rbac/

### Installation
Le conteneur doit être créé dans le namespace par défaut.
```bash
$ helm repo add hashicorp https://helm.releases.hashicorp.com
$ helm repo update
$ helm install vault hashicorp/vault --set="injector.enabled=true" --set="server.enabled=false" --set "injector.externalVaultAddr=https://{{url}}:8200"

$ kubectl get service --all-namespaces 
NAMESPACE            NAME                                           TYPE           CLUSTER-IP      EXTERNAL-IP    PORT(S)                      AGE
default              vault-agent-injector-svc                       ClusterIP      xxxxxxxxxxxxx   <none>         443/TCP                      
```

### Configuration
- L'utilisation de l'agent Vault Injector nécessite ensuite un compte de service associé au conteneur.
Une demande doit etre faite auprès de la team RSH via un ticket SRS : https://xxxxxxxxxxxxxxxxxxxxxxxxxxx/secure/CreateIssue!default.jspa

```bash
Nom du path Vault :
{{vault_path}}

Responsable du path :
-Nom : LE GALLIC Fabrice
-CUID : {{cuid}}

Namespace, cluster k8s, et sam-account devant obtenir l accès :
-namespaces: {{namespace}}
-cluster k8s : {{cluster}}
-compte: {{CUID Projet}} / {{k8s service account}}
```

- Un compte de service doit être créé et présent pour utiliser Vault Agent Injector avec la méthode d'authentification Kubernetes. Il n'est pas recommandé de lier les rôles Vault au compte de service par défaut.
Pour l'authentification Kubernetes, le compte de service doit être lié à un rôle Vault et à une stratégie accordant l'accès aux secrets souhaités. 

Example: service-account.yml
```
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{service_account_name}}
  namespace: {{namespace}}

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: role-tokenreview-binding-{{namespace}}
  namespace: default
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: system:auth-delegator
subjects:
- kind: ServiceAccount
  name: {{service_account_name}}
  namespace: {{namespace}}
```

- La méthode d'authentification doit être par la suite configurée à l'aide d'annotations dans la config du déploiement du conteneur.

Example: deployment.yml
```bash
template:
  metadata
    annotations:
      vault.hashicorp.com/agent-pre-populate-only: 'true'
      vault.hashicorp.com/agent-inject: 'true'
      vault.hashicorp.com/tls-skip-verify: 'true'
      vault.hashicorp.com/auth-path: 'auth/{{rsh_path}}'
      vault.hashicorp.com/role: '{{service_account_name}}'
      vault.hashicorp.com/agent-inject-secret-foo: "{{local_path}}"
      vault.hashicorp.com/agent-inject-template-foo: |
        {{ with secret "/{{vault_path}}" -}}
          {{ .Data.secret }}
        {{- end }}

spec:
  serviceAccountName: {{service_account_name}}
```
