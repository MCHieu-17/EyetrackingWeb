# k6 summary

scenario: lesson_contents

- http_req_waiting: med=11.940, max=42.506, p(90)=18.665, p(95)=20.212, p(99)=35.800, avg=12.325, min=2.879
- http_req_blocked: avg=0.021, min=0.002, med=0.011, max=0.972, p(90)=0.014, p(95)=0.018, p(99)=0.345
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_connecting: max=0.865, p(90)=0.000, p(95)=0.000, p(99)=0.224, avg=0.008, min=0.000, med=0.000
- iterations: count=238.000, rate=23.406
- http_req_sending: avg=0.045, min=0.006, med=0.041, max=0.343, p(90)=0.056, p(95)=0.074, p(99)=0.243
- http_req_failed: rate=0.000
- http_req_duration: med=12.142, max=42.623, p(90)=18.800, p(95)=20.385, p(99)=36.424, avg=12.479, min=2.929
- http_req_duration{expected_response:true}: avg=12.479, min=2.929, med=12.142, max=42.623, p(90)=18.800, p(95)=20.385, p(99)=36.424
- vus: min=5.000, max=5.000
- http_req_receiving: p(95)=0.267, p(99)=0.349, avg=0.109, min=0.009, med=0.073, max=0.378, p(90)=0.235
