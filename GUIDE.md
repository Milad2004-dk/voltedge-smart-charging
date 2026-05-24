# Trin-for-trin guide: kør, push og deploy MVP'en

Denne guide tager jer fra koden paa jeres maskine til et live API paa Azure -
samme slags opsaetning som del 2, men hvor API + database koerer samlet i Docker.
Foelg den i raekkefoelge. I behoever ikke forstaa alt foerste gang; gør trinene,
og det giver mening undervejs.

---

## 0. Vaerktoejer I skal have installeret

- **Git** - til versionsstyring (git-scm.com)
- **Docker Desktop** - til at koere API + database lokalt (docker.com)
- **Python 3.11+** - til at koere tests lokalt (python.org)
- En **GitHub-konto** og en **Azure-konto** (I har studieadgang via KEA)

---

## 1. Kør og test MVP'en lokalt (paa jeres egen maskine)

1. Aabn en terminal i mappen `voltedge-smart-charging`.
2. Start hele løsningen (API + MySQL) med Docker:

   ```bash
   docker compose up --build
   ```

3. Aabn i browseren: `http://localhost:8000/docs` (Swagger UI).
4. Klik paa `POST /charging-plans` -> "Try it out", indsaet eksemplet fra
   README, og klik "Execute". I skal faa et ladeskema retur.
5. Stop igen med `Ctrl+C`.

Kør ogsaa testene (uden Docker):

```bash
pip install -r requirements-dev.txt
pytest -v
ruff check .
```

Naar alt er groent lokalt, er I klar til at laegge det paa GitHub.

---

## 2. Læg koden paa GitHub

1. Gaa til github.com -> **New repository** -> navn fx `voltedge-smart-charging`
   -> **Public** -> opret (uden README, da vi allerede har én).
2. I terminalen i projektmappen:

   ```bash
   git init
   git add .
   git commit -m "Initial commit - Smart Charging MVP"
   git branch -M main
   git remote add origin https://github.com/<JERES-BRUGER>/voltedge-smart-charging.git
   git push -u origin main
   ```

3. Gaa til fanen **Actions** paa GitHub. CI/CD-pipelinen koerer nu automatisk:
   den linter, koerer tests og opretter databaseskemaet. Den skal blive **groen**.
   (Deploy-trinet fejler indtil vi har sat Azure op i trin 4 - det er forventet.)

---

## 3. Opret en Azure Virtual Machine (Ubuntu)

1. I Azure Portal: **Create a resource -> Virtual machine**.
2. Vaelg:
   - Image: **Ubuntu Server 22.04 LTS**
   - Size: **B1s** eller **B2s** (billigt, nok til en MVP)
   - Authentication: **Password** (saet brugernavn + et staerkt password -
     dem bruger vi i GitHub Secrets, ligesom i del 2)
   - Inbound ports: tillad **SSH (22)**
3. Opret VM'en, og notér dens **offentlige IP-adresse**.
4. Aabn port **8000** (saa API'et kan naas udefra):
   VM -> **Networking** -> **Add inbound port rule** -> Destination port `8000`
   -> Protocol TCP -> Allow.
5. Tillad password-login: SSH ind (se trin 4) og saet i
   `/etc/ssh/sshd_config`: `PasswordAuthentication yes`, derefter
   `sudo systemctl restart ssh`.

---

## 4. Installer Docker paa VM'en

SSH ind paa serveren (skift IP og brugernavn ud):

```bash
ssh <VM_USER>@<PUBLIC_IP>
```

Installer Docker + compose-pluginet:

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker $USER
# log ud og ind igen, saa I kan koere docker uden sudo
exit
```

SSH ind igen, og hent koden ned paa serveren:

```bash
git clone https://github.com/<JERES-BRUGER>/voltedge-smart-charging.git
cd voltedge-smart-charging
docker compose up -d --build
```

Test live i browseren: `http://<PUBLIC_IP>:8000/docs`.

---

## 5. Automatisk deploy via GitHub Actions (CD)

Saa I ikke skal SSH'e manuelt hver gang, deployer pipelinen automatisk naar I
pusher til `main`.

1. Paa GitHub: **Settings -> Secrets and variables -> Actions -> New repository
   secret**. Opret tre secrets:
   - `VM_HOST` = serverens offentlige IP
   - `VM_USER` = jeres VM-brugernavn
   - `VM_PASSWORD` = jeres VM-password
2. Pipelinen (`.github/workflows/ci-cd.yml`) gør nu foelgende ved push til main:
   koerer CI (lint + tests + DB-skema), og hvis groent, SSH'er den ind paa VM'en,
   tager `git pull` og `docker compose up -d --build`.
3. Push en lille aendring og se under **Actions**, at baade `test` og `deploy`
   bliver groenne.

---

## 6. Optag video-demo

Optag en kort skaermoptagelse (fx med Xbox Game Bar / Loom) der viser:

1. Repoet paa GitHub + en groen CI/CD-koersel.
2. Et `POST /charging-plans`-kald i Swagger paa den live IP, der returnerer et
   ladeskema (vis at den lader i de billige timer).
3. `GET /charging-plans/{id}` der henter planen igen (beviser at den ligger i
   databasen).

---

## Tjekliste foer aflevering

- [ ] Public GitHub-repo med README
- [ ] Groen CI/CD (baade test- og deploy-job)
- [ ] Live API paa Azure (Swagger naaes paa den offentlige IP)
- [ ] DDD-byggeklodserne ses som klasser i `domain.py`
- [ ] Klasse-/ER-diagram i rapporten (afsnit 4) - vi laver det naar vi skriver afsnittet
- [ ] Video-demo
