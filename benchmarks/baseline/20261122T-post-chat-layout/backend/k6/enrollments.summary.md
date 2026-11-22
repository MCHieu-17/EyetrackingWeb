# k6 summary

scenario: enrollments

- http_req_duration{expected_response:true}: max=76.595, p(90)=6.986, p(95)=7.162, p(99)=70.575, avg=6.225, min=1.076, med=4.455
- http_req_failed: rate=0.000
- http_req_waiting: p(90)=6.773, p(95)=6.944, p(99)=70.473, avg=6.046, min=1.032, med=4.279, max=76.502
- http_req_connecting: p(95)=0.000, p(99)=0.119, avg=0.002, min=0.000, med=0.000, max=0.123, p(90)=0.000
- http_req_duration: min=1.076, med=4.455, max=76.595, p(90)=6.986, p(95)=7.162, p(99)=70.575, avg=6.225
- vus: min=5.000, max=5.000
- http_req_blocked: p(90)=0.013, p(95)=0.015, p(99)=0.170, avg=0.014, min=0.003, med=0.011, max=0.177
- http_req_receiving: p(90)=0.218, p(95)=0.265, p(99)=0.416, avg=0.141, min=0.010, med=0.127, max=0.512
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- http_req_sending: avg=0.039, min=0.010, med=0.040, max=0.071, p(90)=0.050, p(95)=0.054, p(99)=0.065
- iterations: count=243.000, rate=24.006
