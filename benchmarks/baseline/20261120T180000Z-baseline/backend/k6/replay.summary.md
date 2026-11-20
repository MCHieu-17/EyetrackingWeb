# k6 summary

scenario: replay

- http_req_waiting: max=75.705, p(90)=59.595, p(95)=60.417, p(99)=75.590, avg=50.058, min=19.709, med=53.250
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_failed: rate=0.000
- http_req_duration{expected_response:true}: max=75.909, p(90)=59.877, p(95)=60.530, p(99)=75.814, avg=50.238, min=19.839, med=53.416
- iterations: count=80.000, rate=7.964
- http_req_sending: avg=0.043, min=0.009, med=0.043, max=0.078, p(90)=0.053, p(95)=0.057, p(99)=0.073
- http_req_receiving: avg=0.137, min=0.057, med=0.123, max=0.330, p(90)=0.206, p(95)=0.239, p(99)=0.321
- http_req_blocked: avg=0.015, min=0.002, med=0.011, max=0.150, p(90)=0.015, p(95)=0.017, p(99)=0.144
- http_req_connecting: med=0.000, max=0.108, p(90)=0.000, p(95)=0.000, p(99)=0.106, avg=0.003, min=0.000
- vus: min=2.000, max=2.000
- http_req_duration: avg=50.238, min=19.839, med=53.416, max=75.909, p(90)=59.877, p(95)=60.530, p(99)=75.814
