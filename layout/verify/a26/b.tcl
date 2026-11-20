load ct_cmp_flat
select top cell
box 24.10um 18.80um 24.13um 19.30um
puts "=== layers in a[26] li1 strip"
select area
what
puts "=== net select from li1 strip"
select clear
box 24.10um 18.0um 24.13um 18.1um
select area li
select net
what
puts "BOX_OF_NET [box values]"
puts "=== li1 neighbours near y 19.04"
box 23.0um 18.9um 26.0um 19.2um
select clear
select area li
what
quit
