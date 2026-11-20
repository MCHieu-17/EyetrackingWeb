# k6 summary

scenario: aoi_summary

- http_req_duration{expected_response:true}: p(90)=1299.668, p(95)=1307.930, p(99)=1316.131, avg=1248.420, min=1192.751, med=1249.249, max=1318.181
- http_req_failed: rate=0.000
- http_req_waiting: p(95)=1307.479, p(99)=1315.524, avg=1248.050, min=1192.482, med=1248.991, max=1317.536, p(90)=1299.311
- vus: min=2.000, max=2.000
- http_req_sending: avg=0.048, min=0.014, med=0.056, max=0.076, p(90)=0.071, p(95)=0.075, p(99)=0.075
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_duration: avg=1248.420, min=1192.751, med=1249.249, max=1318.181, p(90)=1299.668, p(95)=1307.930, p(99)=1316.131
- http_req_connecting: max=0.072, p(90)=0.047, p(95)=0.069, p(99)=0.072, avg=0.010, min=0.000, med=0.000
- iterations: count=14.000, rate=1.379
- http_req_blocked: p(99)=0.104, avg=0.022, min=0.003, med=0.011, max=0.105, p(90)=0.073, p(95)=0.100
- http_req_receiving: avg=0.322, min=0.163, med=0.246, max=1.031, p(90)=0.533, p(95)=0.757, p(99)=0.976
