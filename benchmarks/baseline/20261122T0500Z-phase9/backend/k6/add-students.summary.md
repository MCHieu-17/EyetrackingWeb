# k6 summary

scenario: add_students

- http_req_blocked: max=0.403, p(90)=0.015, p(95)=0.032, p(99)=0.195, avg=0.020, min=0.003, med=0.011
- http_req_waiting: min=8.603, med=22.782, max=1049.910, p(90)=29.663, p(95)=35.880, p(99)=1042.267, avg=46.795
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_duration: min=8.712, med=23.075, max=1050.050, p(90)=29.892, p(95)=36.202, p(99)=1042.448, avg=47.033
- http_req_failed: rate=0.012
- http_req_duration{expected_response:true}: min=8.712, med=22.484, max=1050.050, p(90)=29.586, p(95)=35.339, p(99)=243.520, avg=34.766
- http_req_connecting: p(95)=0.000, p(99)=0.134, avg=0.006, min=0.000, med=0.000, max=0.278, p(90)=0.000
- http_req_receiving: med=0.045, max=0.244, p(90)=0.070, p(95)=0.102, p(99)=0.171, avg=0.052, min=0.014
- http_req_sending: p(90)=0.236, p(95)=0.261, p(99)=0.322, avg=0.185, min=0.040, med=0.188, max=0.384
- vus: min=2.000, max=2.000
- iterations: count=82.000, rate=8.049
