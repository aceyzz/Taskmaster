<img title="42_taskmaster" alt="42_taskmaster" src="./utils/banner.png" width="100%">

<br>

# taskmaster — 42

Daemon gestionnaire de processus inspiré de Supervisor, conçu pour superviser et contrôler l’exécution de programmes sous forme de processus enfants. Il permet de démarrer, arrêter, redémarrer et surveiller des services de manière interactive, tout en garantissant leur disponibilité grâce à des règles de contrôle configurables. L’application fonctionne au premier plan et expose un shell intégré, assurant un pilotage simple et direct sans architecture client-serveur.  

<br>

## Description

Chaque service est défini dans un fichier YAML et exécuté comme un processus isolé, avec son propre environnement, répertoire de travail, `umask`, flux `stdout`/`stderr` et stratégie de redémarrage. Taskmaster surveille l’état de chaque instance de service en continu et applique la politique de reprise appropriée en cas d’arrêt ou de crash. Une reconfiguration à chaud permet de modifier dynamiquement la supervision sans interrompre les services inchangés, garantissant une continuité d’exécution.  

### Architecture

Taskmaster repose sur une organisation modulaire :  
– **`ServiceHandler`** agit comme orchestrateur central, regroupant la gestion du cycle de vie, le monitoring continu et la reconfiguration dynamique.  
– **`LifecycleMixin`** gère le démarrage, l’arrêt, le redémarrage et la suppression des services.  
– **`MonitorMixin`** surveille les services en tâche de fond et applique les stratégies d’autorestart.  
– **`ReloadMixin`** détecte les modifications de configuration, ajoute/supprime/actualise les services et préserve ceux qui n’ont pas changé.  
– **`Service`** encapsule l’exécution d’un processus enfant et assure sa stabilité (starttime, stopsignal, stoptime, exitcodes…).  
– **`ServiceMonitor`** exécute la boucle de supervision asynchrone.  
– **`ControlShell`** fournit une interface non-bloquante avec autocomplétion, historique et commandes de contrôle.  
– **`Config`** charge et valide strictement les fichiers YAML et normalise les définitions des services.  

### Caractéristiques techniques

– Fonctionnement 100 % asynchrone basé sur asyncio.  
– Support multi-instances via numprocs.  
– Surveillance continue de l’état des processus et détection de crashs précoces.  
– Rechargement dynamique de configuration via reload ou signal SIGHUP, sans désactiver les services non modifiés.  
– Arrêt progressif configurable (stopsignal + timeout) avec fallback en SIGKILL.  
– Redirection sélective des flux stdout/stderr ou mise à la poubelle (/dev/null).  
– Support complet des variables d’environnement, umask octal, working directory et exécution sous un autre utilisateur.  
– Logging complet, horodaté et persisté en fichiers locaux.  
– Shell intégré avec commandes status, start, stop, restart, reload, exit.  

<br>

## Utilisation

Voici les différentes étapes pour utiliser et tester Taskmaster avec Docker et les fichiers de configuration YAML fournis.

1. Préparer l'environnement Docker

```bash
docker-compose up -d --build
docker exec -it taskmaster bash
python3 -m venv ./venv
source ./venv/bin/activate
pip install -r ./requirements.txt
```

<br>

2. Lancer et superviser les processus

a. Lancer un fichier de test

```bash
python3 -m taskmaster -f tests/01_test_child.yaml
```

b. Vérifier les PID

```bash
ps aux | grep taskmaster | grep -v grep
ps aux | grep "sleep 300" | grep -v grep
ps -o pid,ppid,cmd -p <PID_CMD_3>
```

<br>

3. Garder les processus enfants actifs et les redémarrer

```bash
python3 -m taskmaster -f tests/02_keep_child_processes_alive_and_restart.yaml
```
> Vérifiez les logs pour voir si le processus enfant tourne et redémarre plusieurs fois.

<br>

4. Vérifier l'état des processus

Dans un terminal :

```bash
python3 -m taskmaster -f tests/03_processes_are_alive_or_dead.yaml
status
```

Dans un autre terminal :

```bash
ps aux | grep "sleep 300"
kill -9 <PID>
```

Retournez au premier terminal :

```bash
status
```

<br>

5. Recharger la configuration à chaud

```bash
python3 -m taskmaster -f tests/04_loaded_at_launch_and_must_be_reloadable.yaml
```
> Preuve de lancement : vérifiez le fichier de logs.

Modifiez le fichier YAML pour ajouter un service, puis :

```bash
reload
```
> Deux services devraient maintenant tourner.

<br>

6. Modifier les conditions de supervision

```bash
python3 -m taskmaster -f tests/05_changing_their_monitoring_conditions.yaml
```
Actions à effectuer dans le YAML :
- `startretries: 5`
- `exitcodes: [0,1]`
- `autorestart: always`

<br>

7. Modification d’un service sans respawn global

```bash
python3 -m taskmaster -f tests/06_not_de_spawn.yaml
```
Dans le YAML, modifiez :

```yaml
modified_service:
  cmd: /bin/sleep 100
```

Puis :

```bash
reload
```
> Vérifiez dans les logs que seul le service modifié a changé de PID.

<br>

8. Arrêt contrôlé (stop time)

```bash
python3 -m taskmaster -f tests/07_stoptime_validation.yaml
stop stoptime_2sec
stop stoptime_5sec
stop stoptime_10sec
```
> Vérifiez que le temps d’arrêt correspond à la configuration.

<br>

9. Redirection stdout & stderr

```bash
python3 -m taskmaster -f tests/08_stdout_stderr_redirect.yaml
cat /tmp/taskmaster_stdout.log
cat /tmp/taskmaster_stderr.log
cat /tmp/taskmaster_combined.log
cat /tmp/taskmaster_only_stderr.log
grep "This should disappear" /tmp/taskmaster_only_stderr.log
```

<br>

10. Variables d’environnement

```bash
python3 -m taskmaster -f tests/09_env.yaml
cat /tmp/demo_env_output.log
```

<br>

11. Répertoire de travail

```bash
python3 -m taskmaster -f tests/10_workingdir.yaml
cat /tmp/demo_workdir_output.log
ls /tmp/demo_file.txt
```

<br>

12. Umask

```bash
python3 -m taskmaster -f tests/11_umask.yaml
ls -la /tmp/fichier_*.txt
echo "TEST" > /tmp/fichier_normal.txt
cat /tmp/fichier_normal.txt
echo "Attempt" > /tmp/fichier_readonly.txt
```

<br>

## Choix d'implémentation

– Utilisation d’asyncio pour éviter les verrous système complexes et garantir une exécution concurrente prévisible.  
– Découpage en mixins pour séparer clairement les responsabilités et permettre une évolutivité du code.  
– Locks asynchrones pour garantir la cohérence entre les opérations shell et la boucle de monitoring.  
– Démarrage des processus dans des groupes de sessions distincts pour assurer l’arrêt complet de tous les sous-processus.  
– Validation stricte de la configuration via Cerberus pour prévenir les comportements indéterminés lors des reloads.  
– Reload atomique : toutes les modifications sont réalisées sous lock, en bloquant uniquement les opérations critiques sur les services.  
– Politique explicite de gestion des crashs distinguant le “crash précoce” avant stabilisation du “crash inattendu” en cours d’exécution.  

<br>

## Liens utiles

- [Sujet officiel](./utils/subject.pdf)
- [Feuille d'évaluation](./utils/eval.pdf)

<br>

## Grade

<img src="./utils/100.png" alt="Grade" width="150">

<br>

## Auteurs

<table>
	<tr>
		<td align="center">
			<a href="https://github.com/cduffaut" target="_blank">
				<img src="https://img.icons8.com/?size=100&id=tZuAOUGm9AuS&format=png&color=000000" width="40" alt="GitHub Icon"/><br>
				<b>Cécile</b>
			</a>
		</td>
		<td align="center">
			<a href="https://github.com/aceyzz" target="_blank">
				<img src="https://img.icons8.com/?size=100&id=tZuAOUGm9AuS&format=png&color=000000" width="40" alt="GitHub Icon"/><br>
				<b>Cédric</b>
			</a>
		</td>
	</tr>
</table>
