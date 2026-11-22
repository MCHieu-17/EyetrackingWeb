# k6 summary

scenario: session_contents

- http_req_failed: rate=0.000
- http_req_duration: p(99)=19.455, avg=11.595, min=2.718, med=11.505, max=53.559, p(90)=17.683, p(95)=18.580
- http_req_sending: avg=0.041, min=0.010, med=0.040, max=0.225, p(90)=0.053, p(95)=0.060, p(99)=0.083
- iterations: count=238.000, rate=23.322
- http_req_connecting: p(90)=0.000, p(95)=0.000, p(99)=0.070, avg=0.002, min=0.000, med=0.000, max=0.090
- vus: min=5.000, max=5.000
- http_req_blocked: avg=0.013, min=0.003, med=0.011, max=0.119, p(90)=0.014, p(95)=0.017, p(99)=0.096
- http_req_receiving: max=0.306, p(90)=0.174, p(95)=0.206, p(99)=0.264, avg=0.090, min=0.018, med=0.073
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- http_req_duration{expected_response:true}: p(99)=19.455, avg=11.595, min=2.718, med=11.505, max=53.559, p(90)=17.683, p(95)=18.580
- http_req_waiting: p(90)=17.571, p(95)=18.478, p(99)=19.297, avg=11.464, min=2.673, med=11.343, max=53.482
