player = "O"
clear
[6]
game = "........."
round = 0
[0]
if (== (inc round) 9) then (print "egalite !") goto 6
if (== player "O") player = "X"
else player = "O"
print "c'est au joueur" player
[9]
x = int input "x > "
dec x
if (> x 2) then (print "X non valide") goto 9
[1]
y = int input "y > "
dec y
if (> y 2) then (print "Y non valide") goto 1
coo = + x (* y 3)
if (!= 46 at game coo) then (print "case deja jouer") goto 9
tmp = ""
i = 0
[2]
if (== i coo) tmp = cat tmp player
else tmp = cat tmp at game i
write cat at tmp inc i
if (== (% i 3) 0) print
if (< i 9) goto 2
game = tmp
"check win"
i = 0
[3]
n = at game i
if (and (!= n 46) and (== n (at game + i 3)) (== n (at game + i 6))) goto 4
n = at game * i 3
if (== n 46) goto 7
if (and (== n (at game + (* i 3) 1)) (== n (at game + (* i 3) 2))) goto 5
[7]
inc i
if (< i 3) goto 3
n = at game 4
if (== n 46) goto 0
if (and (== n at game 0) (== n at game 8)) goto 8
if (and (== n at game 2) (== n at game 6)) goto 8
goto 0
[4] print "le joueur" player "a gagner verticalement, bravo !!"
goto 6
[5] print "le joueur" player "a gagner horizontalement, bravo !!"
goto 6
[8] print "le joueur" player "a gagner en diagonal, bravo !!"
goto 6
