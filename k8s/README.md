## DOC CSP on k8s
- Install csp environment

```
$ kubectl create secret docker-registry regcred --namespace {{NAMESPACE}}-{{ENV}} --docker-server="https://xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx:5002" --docker-username="{{USERNAME}}" --docker-password="{{PASSWORD}}"

$ kubectl apply -f {{NAMESPACE}}-{{ENV}}-service-account.yml
$ kubectl get secret -n {{NAMESPACE}}-{{ENV}}
NAME                           TYPE                                  DATA   AGE
{{NAMESPACE}}-{{ENV}}-deploy-token-dhrvv     kubernetes.io/service-account-token   3      15s
regcred                                      kubernetes.io/dockerconfigjson        1      55s

$ kubectl apply -f csp-prp-mysql-deployment.yml
$ kubectl apply -f csp-prp-grafana-deployment.yml
$ kubectl apply -f csp-prp-pma-deployment.yml
$ kubectl apply -f csp-prp-aws-cronjob-billing.yml
$ kubectl apply -f csp-prp-fe-cronjob-billing.yml
$ kubectl apply -f csp-prp-apss-cronjob-billing.yml
$ kubectl apply -f csp-prp-az-cronjob-billing.yml
```
