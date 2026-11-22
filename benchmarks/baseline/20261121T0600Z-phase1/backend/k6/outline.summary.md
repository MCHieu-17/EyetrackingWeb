# k6 summary

scenario: outline

- http_req_duration: avg=14.183, min=2.423, med=13.853, max=54.869, p(90)=20.582, p(95)=21.574, p(99)=44.404
- http_req_duration{expected_response:true}: max=54.869, p(90)=20.582, p(95)=21.574, p(99)=44.404, avg=14.183, min=2.423, med=13.853
- http_req_connecting: med=0.000, max=0.112, p(90)=0.000, p(95)=0.000, p(99)=0.108, avg=0.002, min=0.000
- http_req_failed: rate=0.000
- http_req_blocked: max=0.305, p(90)=0.014, p(95)=0.030, p(99)=0.152, avg=0.016, min=0.003, med=0.011
- http_req_waiting: avg=13.985, min=2.378, med=13.644, max=54.727, p(90)=20.307, p(95)=21.410, p(99)=44.285
- vus: min=5.000, max=5.000
- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
- http_req_receiving: p(90)=0.303, p(95)=0.381, p(99)=0.596, avg=0.155, min=0.018, med=0.124, max=0.754
- http_req_sending: p(90)=0.049, p(95)=0.053, p(99)=0.104, avg=0.043, min=0.009, med=0.040, max=0.756
- iterations: count=235.000, rate=23.143
