# k6 summary

scenario: lesson_contents

- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_receiving: p(95)=0.254, p(99)=0.393, avg=0.103, min=0.013, med=0.062, max=0.631, p(90)=0.217
- http_req_sending: p(90)=0.050, p(95)=0.057, p(99)=0.074, avg=0.040, min=0.006, med=0.040, max=0.154
- http_req_duration: avg=13.554, min=3.729, med=10.616, max=38.951, p(90)=20.996, p(95)=21.801, p(99)=37.253
- http_req_failed: rate=0.000
- vus: min=5.000, max=5.000
- http_req_connecting: p(90)=0.000, p(95)=0.000, p(99)=0.099, avg=0.002, min=0.000, med=0.000, max=0.103
- iterations: count=235.000, rate=23.113
- http_req_blocked: p(95)=0.017, p(99)=0.136, avg=0.014, min=0.002, med=0.011, max=0.160, p(90)=0.014
- http_req_waiting: p(99)=37.119, avg=13.410, min=3.670, med=10.488, max=38.867, p(90)=20.797, p(95)=21.711
- http_req_duration{expected_response:true}: p(95)=21.801, p(99)=37.253, avg=13.554, min=3.729, med=10.616, max=38.951, p(90)=20.996
